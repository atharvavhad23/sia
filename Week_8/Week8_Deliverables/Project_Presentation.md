# Project Presentation — SIA RAG Microservice
### The Story of an 8-Week Engineering Sprint

---

## Slide 1: The Problem

**"Financial PDFs are unstructured black boxes."**

- A 150-page annual report contains key data across tables, headers, footnotes, and paragraphs
- Traditional keyword search misses semantic meaning: "profit" ≠ "earnings" ≠ "net income"
- Existing tools require cloud APIs, cost money per query, and leak sensitive documents

**Our goal:** Build a *local-first*, *open-source* system that can understand and query complex PDF documents using modern AI — without any cloud dependency.

---

## Slide 2: What We Built

> **SIA** — Semantic Intelligent Agent

A production-grade **Retrieval-Augmented Generation (RAG) Microservice** that:

1. **Ingests** PDFs using dual extraction engines (PyMuPDF + Camelot)
2. **Understands** documents by splitting them intelligently (LayoutAwareChunker)
3. **Remembers** them as semantic embeddings in a persistent vector database (LanceDB)
4. **Answers** natural language queries by finding the most relevant passages with pinpoint accuracy

**Stack:** FastAPI · Python 3.11 · LanceDB · `all-MiniLM-L6-v2` · Redis · Docker

---

## Slide 3: Architecture

```
┌─────────┐   HTTP   ┌──────────────────────────┐   Cache lookup  ┌───────┐
│ Browser │ ────────▶│      FastAPI Server       │ ───────────────▶│ Redis │
└─────────┘          │  (Uvicorn, 1–N workers)   │◀───────────────┘       │
                     └──────────────┬───────────┘    Cache hit: ~6ms       │
                                    │ Cache miss: ~500ms                    │
                    ┌───────────────┴──────────────┐
                    │         Embedding             │
                    │   all-MiniLM-L6-v2 (384 dim) │
                    └───────────────┬──────────────┘
                                    │
                    ┌───────────────▼──────────────┐
                    │         LanceDB               │
                    │  Cosine similarity search     │
                    │  On-disk PyArrow format       │
                    └──────────────────────────────┘
```

---

## Slide 4: The Architecture Evolution

| Phase | Vector Store | Why Changed |
|---|---|---|
| **Week 4** | FAISS (in-memory) | Zero-dependency baseline for benchmarking |
| **Week 5** | **LanceDB** ✓ | Persistent, on-disk, native metadata filtering — FAISS wiped |

**The key insight:** FAISS requires reloading all embeddings into RAM on every server restart. LanceDB's Apache Lance format persists to disk natively with PyArrow. At 100K+ chunks, this difference is enormous.

---

## Slide 5: The Retrieval Bake-Off (Week 6)

We ran 4 search algorithms against a ground-truth QA dataset:

| Algorithm | Recall@3 | Latency | Verdict |
|---|---|---|---|
| BM25 (keyword) | 0.72 | 3ms | ❌ Misses semantic meaning |
| **Dense Search (LanceDB)** | **1.00** | **18ms** | ✅ **Winner** |
| Hybrid (BM25 + Dense) | 0.95 | 21ms | Near-miss on complex queries |
| Cross-Encoder Reranker | 1.00 | 412ms | Too slow for real-time use |

**Winner:** Dense vector search via LanceDB — **perfect Recall@3 at 18ms latency.**

---

## Slide 6: Finding the Breaking Point (Week 7)

Locust load tests revealed exactly where the system breaks and *why*:

**Concurrency ceiling: ~150 users (single worker)**

| Load | Throughput | p95 Latency | Breaking Point |
|---|---|---|---|
| 100 users, query-only | 47 req/s | 2,000ms | ✅ Stable |
| 500 users | 42 req/s | ~12,000ms | ⚠️ Degrading |
| 100 users, 10% ingest | 12 req/s | 2,800ms | ❌ Breaks |

**Root Cause:** Python's GIL serializes `sentence-transformers` embedding generation across all threads. LanceDB I/O was **not** the bottleneck.

---

## Slide 7: Week 8 Optimizations

### Redis Query Caching
- **What we cache:** Full query results (embedding + search + extractive QA)
- **Cache key:** `SHA-256(query | model | top_k)` — normalized to avoid whitespace cache misses
- **Invalidation:** Explicit purge on every new ingest + 3600s TTL

**Result:** Cache hits serve in **~6ms** vs **~510ms** (85× faster). At 60% hit rate → 4× throughput improvement.

### Docker Compose Stack
```bash
docker compose up  # Starts API + Redis + persistent LanceDB in 3 commands
```

### CI/CD Pipeline
GitHub Actions: lint → test → Docker build → smoke test on every PR.

---

## Slide 8: Current Limits & What's Next

### Current Ceiling
| Constraint | Limit | Fix |
|---|---|---|
| GIL-bound embedding | ~150 users (1 worker) | GPU inference / more workers |
| Bursty PDF ingest | Blocks query traffic at 30 concurrent | Celery/RQ background queue |
| Cache only helps repeated queries | 0% hit rate for unique queries | Semantic similarity cache (ANN on query embeddings) |

### What's Next (Week 9)
- **LLM Integration**: Connect Gemini/Groq API to generate synthesized natural language answers instead of extractive snippets → true conversational RAG
- **Semantic Cache**: Instead of exact-match hashing, use ANN search on query embeddings to find similar past queries and serve cached results for semantically equivalent questions

---

## Slide 9: Key Takeaways

1. **Dense search wins** — when you have good embeddings, BM25 adds complexity for minimal gain
2. **Profile before you cache** — Redis only solved our bottleneck because Week 7 proved what the bottleneck actually was
3. **The GIL is real** — local Python ML inference doesn't scale horizontally without explicit parallelization strategy
4. **LanceDB is production-ready** — zero operational overhead, persistent, and fast enough that it was never the bottleneck

> *"We didn't build a prototype. We built the evidence base for a production architecture decision."*
