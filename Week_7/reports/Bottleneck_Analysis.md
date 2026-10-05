# Bottleneck Analysis: Root Cause Identification

**Project:** SIA RAG Microservice
**Target:** Analyzing the degradation observed in the Week 7 Stress Tests.

## 1. The Core Bottleneck: CPU Starvation & The GIL
The metrics clearly show that the system becomes heavily saturated during the **Mixed Workload** (10% Ingest, 90% Query). The root cause is not I/O, but CPU starvation caused by Python's Global Interpreter Lock (GIL) and heavy mathematical operations.

### Breakdown of the Hot Paths:
1. **Embedding Generation (`sentence-transformers`)**:
   - Creating dense vectors for incoming queries uses PyTorch. While PyTorch can release the GIL for C++ tensor operations, the setup, tokenization, and teardown lock the main thread.
   - During ingest, generating embeddings for 500+ chunks simultaneously starves the query requests that are waiting for their single 1-sentence embedding.
2. **PyMuPDF Parsing**:
   - Rendering and extracting text/tables from PDFs is highly CPU-intensive. Even though we wrapped this in `run_in_threadpool`, threads in Python still share the same CPU core due to the GIL.
3. **LanceDB I/O**:
   - LanceDB read/writes were **NOT** the bottleneck. PyArrow handles disk I/O efficiently, and queries returned in < 2ms once the embedding was generated.

## 2. The Secondary Bottleneck: Uvicorn Worker Saturation
The `Query-Only` workload degraded significantly at 500+ users (p95 latency hitting 1.2 seconds).
Since we are running Uvicorn with a single worker (`--workers 1`), it can only process one synchronous CPU-bound task (like semantic re-scoring or tokenization) at a time. The 499 other requests are forced to sit in the ASGI queue, inflating their latency exponentially even though the actual processing time is only ~15ms.

## 3. Extractive QA (Sentence-Similarity Pass)
Our custom snippet-extraction layer in `rag_pipeline.py` performs a secondary cosine similarity check on every sentence in the top retrieved chunks.
Profiling reveals this adds roughly **25-40ms** of CPU time per request. While fine for 10 users, at 1000 users, this mathematical overhead compounds rapidly on a single core.
