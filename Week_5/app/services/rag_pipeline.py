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

import uuid
import lancedb
import pyarrow as pa
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
# Vector Store wrapper (LanceDB)
# ─────────────────────────────────────────────
class LanceDBVectorStore:
    """
    In-process vector store supporting cosine similarity search,
    metadata filtering, deduplication, and native persistence via LanceDB.
    """

    def __init__(self, dimensionality: int):
        self.dim = dimensionality
        STORE_DIR.mkdir(exist_ok=True)
        self.db = lancedb.connect(str(STORE_DIR / "lancedb"))
        self.table_name = "rag_chunks"
        
        # Define strict pyarrow schema for LanceDB
        self.schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), self.dim)),
            pa.field("chunk_id", pa.string()),
            pa.field("document_id", pa.string()),
            pa.field("source_filename", pa.string()),
            pa.field("extraction_engine", pa.string()),
            pa.field("chunking_strategy", pa.string()),
            pa.field("page_number", pa.int64()),
            pa.field("section_title", pa.string()),
            pa.field("chunk_type", pa.string()),
            pa.field("char_count", pa.int64()),
            pa.field("token_count", pa.int64()),
            pa.field("chunk_index", pa.int64()),
            pa.field("prev_chunk_id", pa.string()),
            pa.field("next_chunk_id", pa.string()),
            pa.field("created_at", pa.string()),
            pa.field("embedding_model", pa.string()),
            pa.field("chunk_text", pa.string()),
        ])

        if self.table_name not in self.db.table_names():
            self.tbl = self.db.create_table(self.table_name, schema=self.schema)
        else:
            self.tbl = self.db.open_table(self.table_name)

        logger.info(f"LanceDBVectorStore initialized (dim={dimensionality}, total={self.count})")

    def clear(self):
        """Wipes the disk files to start fresh."""
        import shutil
        db_path = STORE_DIR / "lancedb"
        if db_path.exists():
            shutil.rmtree(db_path, ignore_errors=True)
        if FAISS_INDEX_FILE.exists():
            FAISS_INDEX_FILE.unlink()
        if METADATA_FILE.exists():
            METADATA_FILE.unlink()
        self.db = lancedb.connect(str(db_path))
        self.tbl = self.db.create_table(self.table_name, schema=self.schema)
        logger.info("LanceDB vector store reset/cleared successfully.")

    # ── persistence ──────────────────────────────────────────────────────
    def save(self):
        # LanceDB automatically flushes to disk during add/insert.
        pass

    @classmethod
    def load(cls, dimensionality: int) -> "LanceDBVectorStore":
        return cls(dimensionality)

    # ── write ─────────────────────────────────────────────────────────────
    def upsert(self, vectors: np.ndarray, metadata_list: List[Dict[str, Any]]):
        """Add vectors + metadata to the store."""
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        vectors = vectors.astype(np.float32)
        
        # Prepare rows for LanceDB
        rows = []
        for i, meta in enumerate(metadata_list):
            row = dict(meta)
            row["vector"] = vectors[i].tolist()
            # Convert datetime to ISO string for PyArrow compatibility
            if isinstance(row.get("created_at"), datetime):
                row["created_at"] = row["created_at"].isoformat()
                
            # Convert UUIDs to strings
            if isinstance(row.get("chunk_id"), uuid.UUID):
                row["chunk_id"] = str(row["chunk_id"])
            if isinstance(row.get("document_id"), uuid.UUID):
                row["document_id"] = str(row["document_id"])
            if isinstance(row.get("prev_chunk_id"), uuid.UUID):
                row["prev_chunk_id"] = str(row["prev_chunk_id"])
            if isinstance(row.get("next_chunk_id"), uuid.UUID):
                row["next_chunk_id"] = str(row["next_chunk_id"])
            
            # Remove nested dicts if any (like table_metadata which LanceDB doesn't need for basic queries)
            row.pop("table_metadata", None)

            
            # Fill missing keys with empty strings to prevent pyarrow null errors
            for field in self.schema.names:
                if field != "vector" and row.get(field) is None:
                    row[field] = 0 if field in ["page_number", "char_count", "token_count", "chunk_index"] else ""

            rows.append(row)

        self.tbl.add(rows)
        logger.info(f"Upserted {len(rows)} vectors to LanceDB (total={self.count})")

    # ── read ──────────────────────────────────────────────────────────────
    def search(
        self, query_vector: np.ndarray, top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Cosine-similarity search. Returns top-k results with scores.
        Note: LanceDB natively calculates distances, so we derive cosine similarity.
        """
        if self.count == 0:
            return []
        
        qv = query_vector.astype(np.float32).flatten()
        # LanceDB defaults to L2 or Cosine distance. We specify cosine.
        res = self.tbl.search(qv).metric("cosine").limit(top_k).to_list()
        
        results = []
        for r in res:
            # Distance is returned. For Cosine Metric in LanceDB: Distance = 1 - CosineSimilarity
            # Therefore: CosineSimilarity = 1 - Distance
            dist = r.pop("_distance", 1.0)
            sim_score = max(0.0, 1.0 - dist)
            r["similarity_score"] = float(round(sim_score, 6))
            results.append(r)
            
        return results

    @property
    def count(self) -> int:
        try:
            return len(self.tbl)
        except Exception:
            return 0


# ─────────────────────────────────────────────
# Pipeline singleton store (module-level)
# ─────────────────────────────────────────────
_vector_store: Optional[LanceDBVectorStore] = None


def get_vector_store(dimensionality: int = 384) -> LanceDBVectorStore:
    global _vector_store
    if _vector_store is None:
        _vector_store = LanceDBVectorStore.load(dimensionality)
    return _vector_store


def reset_vector_store(dimensionality: int = 384) -> None:
    global _vector_store
    if _vector_store is not None:
        _vector_store.clear()
    else:
        _vector_store = LanceDBVectorStore(dimensionality)
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


def _extract_answer_snippets(
    query_text: str,
    results: List[Dict[str, Any]],
    embedder: "BaseEmbedder",
) -> List[Dict[str, Any]]:
    """
    For each retrieved chunk, split its text into sentences and pick the one
    with the highest cosine similarity to the query.
    Adds 'answer_snippet' and 'answer_score' fields to each result dict.
    This gives a focused extractive answer without needing an LLM.
    """
    import re
    import numpy as np

    # Embed the query once (already normalized by embedder)
    query_vec = np.array(embedder.embed_query(query_text), dtype=np.float32)

    # Sentence splitter — split on ., !, ?, or newline followed by whitespace
    _sent_re = re.compile(r'(?<=[.!?\n])\s+')

    for r in results:
        chunk_text: str = (r.get("chunk_text") or "").strip()
        if not chunk_text:
            r["answer_snippet"] = ""
            r["answer_score"] = 0.0
            continue

        # Split into sentences and filter trivially short ones (< 20 chars)
        sentences = [s.strip() for s in _sent_re.split(chunk_text) if len(s.strip()) >= 20]

        # If the chunk is a single sentence or very short, use it as-is
        if len(sentences) <= 1:
            r["answer_snippet"] = chunk_text
            r["answer_score"] = float(round(r.get("similarity_score", 0.0), 4))
            continue

        # Embed all sentences in one batch
        try:
            sent_vecs = np.array(embedder.embed(sentences, batch_size=32), dtype=np.float32)
        except Exception:
            r["answer_snippet"] = sentences[0]
            r["answer_score"] = 0.0
            continue

        # Cosine similarity: dot product on L2-normalized vectors
        scores = sent_vecs @ query_vec  # shape (N,)
        best_idx = int(np.argmax(scores))
        best_score = float(scores[best_idx])

        r["answer_snippet"] = sentences[best_idx]
        r["answer_score"] = round(best_score, 4)

    return results
