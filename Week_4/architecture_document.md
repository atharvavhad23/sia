# Week 4 Architecture Document
## Intelligent Document Processing Pipeline for RAG
**Version:** 1.0  
**Author:** Atharva Ravikiran Avhad  
**Project:** SIA Backend Utilities — PDF Extraction Microservice  

---

## 1. System Overview

This document describes the complete architecture of the Week 4 RAG preprocessing pipeline, which sits **downstream** of the existing Week 3 PDF extraction microservice and converts extracted text into retrieval-ready vector embeddings.

---

## 2. Pipeline Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                  POST /api/v1/ingest                               │
│                  (FastAPI, async)                                   │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
                    ┌──────▼──────┐
                    │  Stage 1    │  ← pdfparser.py (existing, unchanged)
                    │  EXTRACT    │    PyMuPDF / pdfplumber / Camelot
                    │             │    Output: {pages, tables, metadata}
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Stage 2    │  ← chunker.py (new)
                    │   CHUNK     │    Strategies: fixed / recursive /
                    │             │    semantic / layout_aware
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Stage 3    │  ← embedder.py (new)
                    │   EMBED     │    Models: MiniLM / BGE / E5
                    │             │    Output: np.ndarray (L2-normalized)
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Stage 4    │  ← schemas.py (new)
                    │  METADATA   │    Pydantic ChunkMetadata per chunk
                    │             │    prev/next linking, timestamps
                    └──────┬──────┘
                           │
                    ┌──────▼──────┐
                    │  Stage 5    │  ← rag_pipeline.py → FAISS
                    │   STORE     │    IndexFlatIP (cosine via normalized)
                    │             │    Persisted: index.faiss + metadata.json
                    └─────────────┘

  ─────────── At query time ───────────

┌────────────────────────────────────────────────────────────────────┐
│                  POST /api/v1/query                                │
└──────────────────────────┬─────────────────────────────────────────┘
                           │
              Embed query (same model as ingest)
                           │
              FAISS cosine search (top-k × 3)
                           │
              Post-filter by strategy / chunk_type
                           │
              Return top-k {chunk_text + metadata + score}
```

---

## 3. Component Descriptions

### 3.1 Extraction Layer (`pdfparser.py`) — Unchanged
The existing Week 3 extractor. Exposes three engines:
- **fast** (PyMuPDF): ~0.05s/page, raw text only.
- **structural** (pdfplumber): layout-preserving text.
- **hybrid** (Camelot + PyMuPDF in ThreadPoolExecutor): tables + text in parallel.

### 3.2 Chunking Layer (`chunker.py`)
All strategies implement `BaseChunker.chunk(document) -> List[Chunk]`.

| Strategy | Method | Boundary Safety | Speed |
|---|---|---|---|
| `fixed` | tiktoken sliding window | Low (mid-sentence possible) | Fastest |
| `recursive` | Separator hierarchy (\n\n → \n → . → word) | Medium | Fast |
| `semantic` | Cosine similarity breakpoints | High (meaning-aware) | Slow (model load) |
| `layout_aware` | Heading detection + table boundaries | Highest | Fast |

### 3.3 Embedding Layer (`embedder.py`)
All models implement `BaseEmbedder.embed(texts) -> np.ndarray`.

| Model | Dim | Speed | Quality | Use Case |
|---|---|---|---|---|
| `all-MiniLM-L6-v2` | 384 | ~5ms/chunk | Good | High-throughput pipelines |
| `BAAI/bge-small-en-v1.5` | 384 | ~6ms/chunk | Better | Retrieval-optimized tasks |
| `intfloat/e5-base-v2` | 768 | ~15ms/chunk | Best | Accuracy-critical use cases |

### 3.4 Metadata Schema (`schemas.py`)
Every chunk is tagged with a `ChunkMetadata` Pydantic object before storage.
Key fields and their retrieval value:
- `prev_chunk_id` / `next_chunk_id`: enables **context-window expansion** — retrieve surrounding chunks at query time.
- `embedding_model`: ensures retrieval always uses the same model as indexing.
- `chunk_type`: enables type-aware filtering (e.g., return only tables for numerical queries).
- `section_title`: enables section-level scoping at retrieval time.

### 3.5 Vector Store — FAISS (`rag_pipeline.py`)

**Choice: FAISS over Chroma**

| Criterion | FAISS | Chroma |
|---|---|---|
| Setup | In-process, zero config | Requires client/server |
| Benchmark purity | ✅ No network I/O skew | ❌ Adds latency |
| Metadata filtering | ❌ Post-retrieval in Python | ✅ Native |
| Persistence | ✅ .faiss + .json files | ✅ SQLite |
| Production scaling | External DB needed for distributed | Better for multi-node |

**Decision:** FAISS chosen for Week 4 due to benchmarking purity and zero external dependencies. For production at scale, migrate to Chroma or Weaviate for native metadata filtering.

Index type: `IndexFlatIP` (inner product on L2-normalized vectors = cosine similarity).

---

## 4. Async Architecture
All five pipeline stages run inside `run_in_threadpool()` (inherited from Week 3 architecture), keeping the FastAPI event loop unblocked during heavy CPU/IO operations.

---

## 5. Integration with Existing Service
- `/api/v1/extract` (Week 3): **unchanged** — still works independently.
- `/api/v1/ingest` (Week 4): additive, calls the same `pdfparser.py` internally.
- `/api/v1/query` (Week 4): new retrieval endpoint, fully independent.
- No existing tests were broken (all 14 Week 3 tests + new RAG tests pass).
