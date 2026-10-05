# Deployment Guide — SIA RAG Microservice

> **Audience**: A new engineer with zero prior context on this project. You should be able to go from a fresh clone to a running, healthy system by following this document top to bottom.

---

## 1. Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Docker | ≥ 24.0 | Required for containerized deployment |
| Docker Compose | ≥ 2.20 | Bundled with Docker Desktop |
| Python | 3.11 | Required only for local non-Docker dev |
| Git | Any | To clone the repository |

**Hardware minimums** (from Week 7 load testing on a single machine):
- CPU: 4 cores (2 minimum, 4 to handle ≥150 concurrent users)
- RAM: 4 GB (the MiniLM model loads ~250 MB; LanceDB uses ~200 MB)
- Disk: 1 GB free for the Docker images + LanceDB data volume

---

## 2. Environment Variables and Secrets

```bash
# 1. Copy the example file
cp .env.example .env

# 2. Edit .env as needed. Minimum required changes for production:
#    - Set UVICORN_WORKERS to (2 × CPU cores + 1)
#    - Set REDIS_CACHE_TTL_SECONDS based on your document update frequency
```

Key variables to review (see `.env.example` for the full list):

| Variable | Safe Default | When to Change |
|---|---|---|
| `UVICORN_WORKERS` | `1` | Increase for > 150 concurrent users |
| `REDIS_CACHE_TTL_SECONDS` | `3600` | Decrease if documents update frequently |
| `REDIS_ENABLED` | `true` | Set `false` to profile raw embedding latency |

---

## 3. Docker Compose Deployment Steps

```bash
# Step 1: Clone the repository
git clone <repo-url>
cd sia-utilities

# Step 2: Configure environment
cp .env.example .env
# Edit .env if needed (defaults work for local testing)

# Step 3: Launch the full stack
docker compose up --build

# Expected output:
# [+] Running 3/3
#  ✔ Network sia_default      Created
#  ✔ Container sia_redis       Healthy
#  ✔ Container sia_api         Healthy
```

> **First-time note**: Docker will pull the Python and Redis base images (~500 MB). Subsequent starts are fast.

---

## 4. Verify a Healthy Deployment

Run these checks in order after `docker compose up`:

```bash
# 1. Basic health check
curl http://localhost:8000/
# Expected: {"status": "online", "service": "SIA Backend Utilities"}

# 2. System metrics (confirms psutil instrumentation)
curl http://localhost:8000/api/v1/health/metrics
# Expected: {"cpu_percent_process": ..., "memory_rss_mb": ...}

# 3. Ingest a PDF (replace with your file path)
curl -X POST http://localhost:8000/api/v1/ingest \
  -F "file=@/path/to/your.pdf" \
  -F "engine=fast" \
  -F "chunking_strategy=layout_aware" \
  -F "embedding_model=minilm"
# Expected: {"success": true, "data": {"chunks_created": N, ...}}

# 4. Run a semantic query
curl -X POST http://localhost:8000/api/v1/query \
  -F "query=What is the main topic of this document?" \
  -F "embedding_model=minilm"
# Expected: {"success": true, "data": {"results": [...], "cache_hit": false}}

# 5. Same query again — should be a cache hit
curl -X POST http://localhost:8000/api/v1/query \
  -F "query=What is the main topic of this document?" \
  -F "embedding_model=minilm"
# Expected: "cache_hit": true, and p50 latency < 10ms
```

---

## 5. Scaling Guidance (Evidence from Week 7)

| Concurrent Users | Configuration | Expected p95 Latency |
|---|---|---|
| < 150 | `UVICORN_WORKERS=1` (default) | < 1.2s |
| 150 – 600 | `UVICORN_WORKERS=4` | < 2.0s |
| 600 – 1,000 | Workers=8 + Redis cache required | < 2.0s for cached queries |
| > 1,000 | **Deploy a message queue** (Celery + Redis) for the ingestion path to prevent CPU contention with query traffic | Depends on cache hit rate |

**Why these numbers?** Week 7 load testing with Locust on a single machine showed that a single Uvicorn worker is CPU-saturated at ~150 users because the MiniLM embedding generation is serialized by the Python GIL. Increasing workers directly distributes this CPU work across cores.

---

## 6. Troubleshooting Common Failure Modes

### API fails to start: `ModuleNotFoundError: No module named 'app'`
**Cause**: You're running `uvicorn` from the wrong directory.  
**Fix**: Always run from the `Week_5/` directory: `cd Week_5 && uvicorn app.main:app`

### Ingest returns `500 Internal Server Error` with PyTorch error
**Cause**: SentenceTransformers is being loaded simultaneously across multiple threads. This is the GIL issue documented in Week 7.  
**Fix**: Don't send concurrent ingest requests. Use the Celery queue pattern for bulk ingestion.

### Query returns `"Vector store is empty"`
**Cause**: No documents have been ingested yet, or the LanceDB volume was wiped.  
**Fix**: Ingest at least one PDF before querying.

### `[WinError 10048] Only one usage of each socket address`
**Cause**: Another process is already using port 8000.  
**Fix**: Kill the existing process: `Get-Process -Id (Get-NetTCPConnection -LocalPort 8000).OwningProcess | Stop-Process`

### LanceDB `LockedError` or corrupted table
**Cause**: A previous process was killed mid-write, leaving a lock file.  
**Fix**: Stop all containers, delete `Week_5/vector_store/lancedb/`, and restart. All ingested documents will need to be re-uploaded.

### Redis connection warnings in logs
**Cause**: Redis is not running (only happens in local dev, not Docker Compose).  
**Fix**: The app is designed to fall back gracefully — queries still work, just without caching. Start Redis: `docker run -d -p 6379:6379 redis:7-alpine`

---

## 7. Rollback Procedure

```bash
# Stop the stack
docker compose down

# Optionally wipe the LanceDB volume (WARNING: loses all ingested data)
docker compose down -v

# Roll back to a previous image tag
docker compose up --build  # Rebuild from source

# Or specify a specific image if you've pushed to a registry
# docker pull your-registry/sia-api:previous-tag
# docker compose up
```
