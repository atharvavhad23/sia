"""
rag_pipeline.py — Day 3: End-to-End RAG Pipeline
==================================================
Wires the full pipeline in sequence:

  Upload → Parse (pdfparser.py) → Chunk (chunker.py)
       → Embed (embedder.py) → Attach Metadata (schemas.py)
       → Store (FAISS) → [later] Query → Retrieve

Vector Store Choice: FAISS
  - Rationale: Zero external services, in-process, ideal for benchmarking
    throughput cleanly (no network I/O skewing results).
  - Persistence: FAISS index + metadata are serialized to disk (JSON + .index)
    so data survives restarts.
  - Tradeoff: No built-in metadata filtering (Chroma wins here); we
    implement lightweight metadata filtering in Python post-retrieval.

All heavy operations (extract, chunk, embed, upsert) run in a ThreadPoolExecutor
to stay consistent with the existing async architecture in app/main.py.
"""

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np

from app.services.chunker import BaseChunker, Chunk, get_chunker
from app.services.embedder import BaseEmbedder, get_embedder
from app.services.pdfparser import PDFParserService
from app.services.schemas import ChunkMetadata, TableMetadata

logger = logging.getLogger("sia.rag_pipeline")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","name":"%(name)s"}'
    ))
    logger.addHandler(handler)
logger.propagate = False

# ─────────────────────────────────────────────
# Paths for persistence
# ─────────────────────────────────────────────
STORE_DIR = Path("vector_store")
FAISS_INDEX_FILE = STORE_DIR / "index.faiss"
METADATA_FILE = STORE_DIR / "metadata.json"


# ─────────────────────────────────────────────
# Vector Store wrapper (FAISS + LanceDB compatible)
# ─────────────────────────────────────────────
class FAISSVectorStore:
    """
    In-process vector store supporting cosine similarity search,
    metadata filtering, deduplication, and persistence.
    """

    def __init__(self, dimensionality: int):
        self.dim = dimensionality
        self.index = faiss.IndexFlatIP(dimensionality)  # cosine via normalized vectors
        self._metadata: List[Dict[str, Any]] = []       # parallel list to FAISS rows
        logger.info(f"FAISSVectorStore initialized (dim={dimensionality})")

    def clear(self):
        """Wipes the in-memory index and disk files to start fresh."""
        self.index = faiss.IndexFlatIP(self.dim)
        self._metadata = []
        if FAISS_INDEX_FILE.exists():
            FAISS_INDEX_FILE.unlink()
        if METADATA_FILE.exists():
            METADATA_FILE.unlink()
        logger.info("Vector store reset/cleared successfully.")

    # ── persistence ──────────────────────────────────────────────────────
    def save(self):
        STORE_DIR.mkdir(exist_ok=True)
        faiss.write_index(self.index, str(FAISS_INDEX_FILE))
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._metadata, f, indent=2, default=str)
        logger.info(f"FAISS index saved ({self.index.ntotal} vectors)")

    @classmethod
    def load(cls, dimensionality: int) -> "FAISSVectorStore":
        store = cls(dimensionality)
        if FAISS_INDEX_FILE.exists() and METADATA_FILE.exists():
            try:
                store.index = faiss.read_index(str(FAISS_INDEX_FILE))
                with open(METADATA_FILE, "r", encoding="utf-8") as f:
                    store._metadata = json.load(f)
                logger.info(f"FAISS index loaded ({store.index.ntotal} vectors)")
            except Exception as e:
                logger.warning(f"Failed to load existing index, starting clean: {e}")
                store.clear()
        else:
            logger.info("No existing FAISS index found — starting fresh")
        return store

    # ── write ─────────────────────────────────────────────────────────────
    def upsert(self, vectors: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """Add vectors + metadata to the store."""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        vectors = vectors.astype(np.float32)
        self.index.add(vectors)
        self._metadata.extend(metadata_list)
        logger.info(f"Upserted {len(metadata_list)} vectors (total={self.index.ntotal})")

    # ── read ──────────────────────────────────────────────────────────────
    def search(
        self, query_vector: np.ndarray, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Cosine-similarity search. Returns top-k results with scores.
        """
        if self.index.ntotal == 0:
            return []
        qv = query_vector.astype(np.float32).reshape(1, -1)
        scores, indices = self.index.search(qv, min(top_k, self.index.ntotal))
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1 or idx >= len(self._metadata):
                continue
            result = dict(self._metadata[idx])
            result["similarity_score"] = float(round(score, 6))
            results.append(result)
        return results

    @property
    def count(self) -> int:
        return self.index.ntotal


# ─────────────────────────────────────────────
# Pipeline singleton store (module-level)
# ─────────────────────────────────────────────
_vector_store: Optional[FAISSVectorStore] = None


def get_vector_store(dimensionality: int = 384) -> FAISSVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore.load(dimensionality)
    return _vector_store


def reset_vector_store(dimensionality: int = 384) -> None:
    global _vector_store
    if _vector_store is not None:
        _vector_store.clear()
    else:
        _vector_store = FAISSVectorStore(dimensionality)
        _vector_store.clear()


# ─────────────────────────────────────────────
# Core pipeline function: ingest
# ─────────────────────────────────────────────
def ingest_document(
    file_path: str,
    source_filename: str,
    chunking_strategy: str = "recursive",
    embedding_model: str = "minilm",
    extraction_engine: str = "fast",
) -> Dict[str, Any]:
    """
    Full pipeline: parse → chunk → embed → attach metadata → store.

    Returns a summary dict with timing and stats for the API response.
    """
    pipeline_start = time.time()
    document_id = str(uuid.uuid4())
    stage_times: Dict[str, float] = {}

    # ── Stage 1: Extract ────────────────────────────────────────────────
    logger.info(f"[{document_id}] Stage 1: Extracting with engine='{extraction_engine}'")
    t0 = time.time()
    if extraction_engine == "fast":
        doc = PDFParserService.extract_fast_text(file_path)
    elif extraction_engine == "structural":
        doc = PDFParserService.extract_structural_text(file_path)
    else:
        doc = PDFParserService.extract_hybrid_text(file_path)
    stage_times["extract_sec"] = round(time.time() - t0, 4)
    logger.info(f"[{document_id}] Extraction done in {stage_times['extract_sec']}s")

    # ── Stage 2: Chunk ──────────────────────────────────────────────────
    logger.info(f"[{document_id}] Stage 2: Chunking with strategy='{chunking_strategy}'")
    t0 = time.time()
    chunker: BaseChunker = get_chunker(chunking_strategy)
    chunks: List[Chunk] = chunker.chunk(doc)
    stage_times["chunk_sec"] = round(time.time() - t0, 4)
    logger.info(f"[{document_id}] Chunking done — {len(chunks)} chunks in {stage_times['chunk_sec']}s")

    if not chunks:
        return {
            "document_id": document_id,
            "source_filename": source_filename,
            "chunks_created": 0,
            "warning": "No chunks produced — document may be empty or image-only",
            "stage_times": stage_times,
        }

    # ── Stage 3: Embed ──────────────────────────────────────────────────
    logger.info(f"[{document_id}] Stage 3: Embedding with model='{embedding_model}'")
    t0 = time.time()
    embedder: BaseEmbedder = get_embedder(embedding_model)
    texts = [c.text for c in chunks]
    vectors: np.ndarray = embedder.embed(texts, batch_size=32)
    stage_times["embed_sec"] = round(time.time() - t0, 4)
    logger.info(f"[{document_id}] Embedding done in {stage_times['embed_sec']}s")

    # ── Stage 4: Attach Metadata ────────────────────────────────────────
    logger.info(f"[{document_id}] Stage 4: Attaching metadata")
    metadata_list: List[Dict[str, Any]] = []
    chunk_ids = [str(uuid.uuid4()) for _ in chunks]

    for i, (chunk, chunk_id) in enumerate(zip(chunks, chunk_ids)):
        meta = ChunkMetadata(
            chunk_id=chunk_id,
            document_id=document_id,
            source_filename=source_filename,
            extraction_engine=extraction_engine,
            chunking_strategy=chunking_strategy,
            page_number=chunk.page_number,
            section_title=chunk.section_title,
            chunk_type=chunk.chunk_type,
            char_count=chunk.char_count,
            token_count=chunk.token_count,
            chunk_index=i,
            prev_chunk_id=chunk_ids[i - 1] if i > 0 else None,
            next_chunk_id=chunk_ids[i + 1] if i < len(chunks) - 1 else None,
            created_at=datetime.now(timezone.utc),
            embedding_model=embedder.model_name,
            table_metadata=TableMetadata(
                rows=chunk.source_metadata.get("rows"),
                columns=chunk.source_metadata.get("columns"),
            ),
        )
        entry = meta.model_dump()
        entry["chunk_text"] = chunk.text          # store text for retrieval display
        metadata_list.append(entry)

    # ── Stage 5: Store ──────────────────────────────────────────────────
    logger.info(f"[{document_id}] Stage 5: Upserting to FAISS")
    t0 = time.time()
    store = get_vector_store(dimensionality=embedder.dimensionality)
    store.upsert(vectors, metadata_list)
    store.save()
    stage_times["store_sec"] = round(time.time() - t0, 4)
    total_time = round(time.time() - pipeline_start, 4)
    logger.info(f"[{document_id}] Pipeline complete in {total_time}s | total_vectors={store.count}")

    return {
        "document_id": document_id,
        "source_filename": source_filename,
        "extraction_engine": extraction_engine,
        "chunking_strategy": chunking_strategy,
        "embedding_model": embedder.model_name,
        "chunks_created": len(chunks),
        "total_vectors_in_store": store.count,
        "stage_times_sec": stage_times,
        "total_pipeline_time_sec": total_time,
    }


# ─────────────────────────────────────────────
# Core pipeline function: query
# ─────────────────────────────────────────────
def query_documents(
    query_text: str,
    embedding_model: str = "minilm",
    top_k: int = 5,
    filter_strategy: Optional[str] = None,
    filter_chunk_type: Optional[str] = None,
    filter_filename: Optional[str] = None,
    filter_document_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Embed query → cosine similarity search → deduplicate & filter → return top-k results.
    """
    t0 = time.time()
    embedder: BaseEmbedder = get_embedder(embedding_model)
    store = get_vector_store(dimensionality=embedder.dimensionality)

    if store.count == 0:
        return {
            "query": query_text,
            "results": [],
            "message": "Vector store is empty. Please upload and ingest a PDF first.",
        }

    # Query expansion: optional prefix/suffix manipulation could go here
    query_vector = embedder.embed_query(query_text)
    # Fetch extra candidates to account for filtering and deduplication
    raw_results = store.search(query_vector, top_k=max(top_k * 4, 20))

    filtered = []
    seen_snippets = set()
    
    # Calculate global max for re-normalization
    max_score = raw_results[0].get("similarity_score", 1.0) if raw_results else 1.0

    for r in raw_results:
        # Metadata filters
        if filter_strategy and r.get("chunking_strategy") != filter_strategy:
            continue
        if filter_chunk_type and r.get("chunk_type") != filter_chunk_type:
            continue
        if filter_filename and filter_filename.lower() not in (r.get("source_filename") or "").lower():
            continue
        if filter_document_id and r.get("document_id") != filter_document_id:
            continue

        # Deduplicate identical or highly overlapping text
        text_snippet = (r.get("chunk_text") or "").strip()[:100]
        if text_snippet in seen_snippets:
            continue
        seen_snippets.add(text_snippet)

        # Format confidence percentage (re-normalized against the top match)
        score = r.get("similarity_score", 0.0)
        match_pct = max(0, min(100, int((score / (max_score or 1.0)) * 100)))
        r["match_percentage"] = f"{match_pct}%"

        filtered.append(r)
        if len(filtered) >= top_k:
            break

    results = filtered[:top_k]

    # ── Extractive QA: find the best-matching sentence per result ───────
    if results:
        results = _extract_answer_snippets(query_text, results, embedder)

    elapsed = round(time.time() - t0, 4)
    logger.info(f"Query '{query_text}' returned {len(results)} results in {elapsed}s")

    return {
        "query": query_text,
        "embedding_model": embedder.model_name,
        "total_results": len(results),
        "query_time_sec": elapsed,
        "results": results,
    }
