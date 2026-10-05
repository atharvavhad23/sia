# Final Engineering Report — SIA RAG Microservice
### 8-Week Build: From PDF Extraction to Production-Ready Retrieval System

**Author:** Atharva Ravikiran Avhad  
**Manager:** Aditya Chauhan  
**Date:** October 2026

---

## Executive Summary

Over 8 weekly sprints, we designed, built, benchmarked, and hardened a local-first **Retrieval-Augmented Generation (RAG) microservice** — codenamed **SIA**. Starting from raw PDF extraction in Week 1, the system evolved through an intelligent chunking pipeline, a swappable embedding architecture, an evidence-based vector database migration, a multi-algorithm retrieval bake-off, a load-tested concurrency ceiling, and finally a production-packaged, Docker Compose–deployable service with Redis caching and CI/CD.

**Final State:** A FastAPI microservice that can ingest PDFs, store 384-dimensional dense embeddings in LanceDB, and serve semantic search results with extractive QA answers at ~47 req/s (un-cached) or >185 req/s (with Redis, 60% hit rate) on a single CPU machine.

---

## Week-by-Week Engineering Decisions

### Weeks 1–2: Foundation — FastAPI & Dual-Engine PDF Extraction
Built a FastAPI REST service with two extraction engines:
- **PyMuPDF** (`fast`): C-speed text extraction, ~50ms per document
- **Camelot** (`structural`): Table-aware extraction, ~800ms

**Key design decision:** Decoupled extraction from chunking/embedding from the start using a plugin interface (`BaseChunker`, `BaseEmbedder`), enabling future swapping without touching the API layer.

### Week 3: Production Hardening
- **14 pytest tests** covering edge cases: zero-page PDFs, corrupted files, empty uploads
- **Custom exception classes** (`PDFCorruptedException`, `PDFPasswordProtectedException`)
- **Structured JSON logging** — every request logs in machine-parseable format
- **`run_in_threadpool`** — moved all CPU-heavy PDF work off the async event loop

### Week 4: RAG Pipeline v1 — FAISS + LayoutAwareChunker
- **LayoutAwareChunker**: Splits on document structure (headers → paragraphs → sentences) preserving semantic coherence
- **FAISS** in-memory vector index with `all-MiniLM-L6-v2` embeddings (384 dims)
- **RAG Studio UI**: Custom interactive web interface replacing default Swagger docs

### Week 5: Vector Database Migration — FAISS → LanceDB
Benchmarked LanceDB against FAISS on insertion throughput, concurrent query latency, and storage efficiency. **Key findings:**
- LanceDB: persistent on-disk (survives restarts), native PyArrow columnar format
- LanceDB: metadata filtering built-in (vs. Python post-filter in FAISS)
- **Fixed PyArrow bug:** UUID objects must be explicitly cast to `str()` before insertion
- **Migrated to LanceDB** as the production vector store. FAISS fully removed.

### Week 6: Retrieval Bake-Off — Finding the Best Search Algorithm
Benchmarked 4 retrieval strategies on a ground-truth QA dataset derived from the Godrej financial report:

| Algorithm | Recall@3 | MRR | Latency |
|---|---|---|---|
| BM25 (sparse) | 0.72 | 0.71 | 3ms |
| **Dense (LanceDB)** | **1.00** | **1.00** | **18ms** |
| Hybrid (RRF) | 0.95 | 0.92 | 21ms |
| Cross-Encoder Reranker | 1.00 | 1.00 | 412ms |

**Decision:** Dense search via LanceDB is the clear winner — perfect recall at production-viable latency. The Cross-Encoder achieves equal recall but at 23× higher latency, making it unsuitable for real-time queries.

### Week 7: Scalability — Finding the Concurrency Ceiling
Locust load tests (100/500/1000 concurrent users) using two profiles:

**Query-Only Load (no ingest):**
| Users | Throughput | p95 Latency | Error Rate |
|---|---|---|---|
| 100 | 47 req/s | 2,000ms | 0% |
| 500 | ~42 req/s | degrades → timeouts | 12%+ |

**Root Cause:** Single Uvicorn worker saturates at ~150 users because `sentence-transformers` embedding is CPU-bound and serialized by Python's GIL. LanceDB I/O was **not** the bottleneck (sub-2ms reads).

**Mixed Load (10% ingest + 90% query):** System breaks at 30 concurrent users. PyMuPDF parsing + embedding generation compete for the same CPU core, triggering cascading queue overflow.

### Week 8: Optimization & Handover

#### Redis Caching (Targeting the Proven Bottleneck)
**What we cached:** Full query results (embedding + LanceDB search + extractive QA output)  
**Cache key:** `SHA-256(normalized_query | model | top_k)`  
**Invalidation:** TTL (3600s) + explicit purge on document ingest  
**Result:** Cache hits serve in ~6ms vs ~510ms (p50). ~4× throughput improvement at 60% hit rate.  
**Honest note:** Cache hit rate is near 0% for fully unique queries — Redis only helps when users repeat questions.

#### Docker Compose Stack
Full stack: FastAPI + Redis + persistent LanceDB volume. Health checks and `depends_on` ordering ensure Redis is ready before the API accepts connections.

#### CI/CD Pipeline
GitHub Actions on push/PR: lint (flake8 + black), Week 3 pytest suite, Docker build verification, container smoke test.

---

## Performance Summary (All Weeks)

| Metric | Value | Context |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2` | 384 dims, ~50ms per batch on CPU |
| Single query latency (no cache) | 200–500ms | Dominated by embedding generation |
| Single query latency (cache hit) | 5–15ms | Redis lookup only |
| Max throughput (1 worker, no cache) | 47 req/s | Week 7 measurement |
| Max throughput (1 worker, 60% cache) | 185+ req/s | Week 8 measurement |
| Safe concurrency ceiling | ~150 users | Before p95 > 2s |
| Dense search Recall@3 | 1.00 | Week 6 bake-off |

---

## Known Limitations & Next Steps

1. **GIL bottleneck at scale**: The fundamental constraint is Python's GIL serializing embedding generation. Solution: GPU inference (PyTorch CUDA) or a dedicated embedding microservice.
2. **Ingest blocks query traffic**: Move PDF ingestion to a Celery/RQ background queue for production.
3. **No LLM integration**: The system returns extractive snippets, not synthesized answers. Adding Gemini/Groq as an LLM layer (Week 9 goal) would enable true conversational RAG.
4. **Single-node LanceDB**: Not horizontally scalable. For multi-replica deployments, migrate to a distributed vector DB (Weaviate, Qdrant).
