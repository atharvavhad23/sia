# Stress Testing Report: SIA RAG Microservice

**Date:** September 25, 2026
**Framework:** Locust
**Target:** SIA RAG Microservice (FastAPI, LanceDB, MiniLM)

## 1. Methodology
We executed a progressive load test hitting two primary workloads:
1. **Query-Only Load**: Simulates read-heavy traffic focusing exclusively on the `/api/v1/search` endpoint (embedding + vector retrieval).
2. **Mixed Load (90/10)**: Simulates realistic production traffic where 90% of requests are queries and 10% are heavy PDF ingestions targeting `/api/v1/ingest`.

Each scenario was run against a single `uvicorn` worker at concurrency levels of 100, 500, and 1000 users.

## 2. Benchmark Results

### Query-Only Workload (100% Reads)
*Measures embedding generation and LanceDB vector lookup efficiency.*

| Concurrent Users | Throughput (req/sec) | p50 Latency | p95 Latency | Error Rate |
|------------------|----------------------|-------------|-------------|------------|
| 100              | ~45 req/s            | 35 ms       | 120 ms      | 0.0%       |
| 500              | ~42 req/s            | 180 ms      | 1,200 ms    | 0.0%       |
| 1000             | ~38 req/s            | 850 ms      | 4,500 ms    | 1.2% (Timeout) |

**Observation**: The system handles up to ~100 users flawlessly. At 500+ users, queueing at the single Uvicorn worker causes exponential latency growth.

### Mixed Workload (90% Query / 10% Ingest)
*Measures CPU contention between PyMuPDF/Chunking and Embedding Generation.*

| Concurrent Users | Throughput (req/sec) | p50 Latency | p95 Latency | Error Rate |
|------------------|----------------------|-------------|-------------|------------|
| 100              | ~12 req/s            | 450 ms      | 2,800 ms    | 0.5%       |
| 500              | ~8 req/s             | 3,200 ms    | 12,000 ms   | 14.0%      |
| 1000             | ~4 req/s             | 14,000 ms   | 35,000 ms   | 42.0%      |

**Observation**: The introduction of heavy PDF parsing obliterates query latency. The CPU becomes saturated by PyMuPDF and SentenceTransformers simultaneously, causing massive queueing and connection timeouts.

## 3. Resource Utilization Summary
- **Memory (RSS)**: Peaked at ~450MB during query load. Spiked to ~1.2GB during mixed load due to in-memory PDF page rendering. No obvious memory leaks were detected.
- **CPU**: Pegged at 100% on a single core during embedding and ingestion due to Python's Global Interpreter Lock (GIL).

*See the `charts/` directory for detailed timeseries visualisations of throughput vs latency.*
