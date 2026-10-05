# Capacity Planning & Infrastructure Recommendations

**Project:** SIA RAG Microservice
**Objective:** Define the safe operating ceiling of the current architecture and recommend infrastructure upgrades to raise that ceiling.

## 1. Safe Operating Ceiling (Current Architecture)
Based on the stress test data, our Acceptable SLAs are defined as:
- **p95 Latency**: < 2.0 seconds
- **Error Rate**: < 1.0%

**Current Capacity:**
- **Query-Only Load**: The current single-worker FastAPI setup can safely sustain **~150 concurrent users**. Beyond this, p95 latency crosses the 2.0s threshold due to ASGI queueing.
- **Mixed Load (Ingest + Query)**: The system can only safely sustain **~30 concurrent users**. The CPU-heavy PyMuPDF extraction instantly degrades query performance for all active users.

---

## 2. Infrastructure Recommendations (To Scale to 1000+ Users)

To hit the 1000+ user requirement, we must decouple our CPU-bound tasks and break free of the Python GIL.

### Recommendation 1: Horizontal Scaling (Uvicorn Workers)
**The Problem**: A single Uvicorn worker limits us to a single CPU core.
**The Fix**: Since our LanceDB vector store is on-disk and the FastAPI app is stateless, we can safely launch Uvicorn with multiple workers (`uvicorn app.main:app --workers 4`). This will immediately distribute the embedding queue across multiple cores, potentially quadrupling our Query-Only capacity to ~600 users.

### Recommendation 2: Asynchronous Message Queue for Ingestion
**The Problem**: PDF Ingestion steals CPU cycles from semantic search queries, violating user UX SLAs.
**The Fix**: Remove `/api/v1/ingest` from the synchronous critical path.
- Implement **Celery** or **RQ** (Redis Queue).
- When a user uploads a PDF, the API instantly returns a `202 Accepted` with a `task_id`.
- A separate background worker pool on an isolated CPU core handles the PyMuPDF parsing and LanceDB insertion.
- This entirely protects search latency from ingestion spikes.

### Recommendation 3: Caching Semantic Queries
**The Problem**: Repeating the same query requires running the SentenceTransformer model repeatedly, wasting CPU cycles.
**The Fix**: Implement a **Redis Cache** in front of the `/api/v1/search` endpoint. Map the raw string `query` to the generated embedding array (or the exact LanceDB output). If a query is cached, we bypass the transformer entirely, serving the response in < 2ms.

### Recommendation 4: GPU Acceleration for Embeddings
**The Problem**: CPU-based embeddings are too slow for real-time scale.
**The Fix**: Migrate the deployment environment to hardware with an NVIDIA GPU (or AWS g4dn instance) and ensure PyTorch uses CUDA. This will reduce embedding latency from ~15ms to ~1ms and allow batching of concurrent requests natively.
