"""
locustfile_query_cached.py — Week 8 Cache Benchmark
=====================================================
Reuses the exact Week 7 query-only methodology with Redis caching enabled.
Run this AFTER running Week_7/locustfiles/locustfile_query.py to get
directly comparable numbers.

Command:
  locust -f Week_8/benchmarks/locustfile_query_cached.py \
         --headless -u 100 -r 20 --run-time 2m \
         --host http://127.0.0.1:8000 \
         --csv Week_8/benchmarks/cached_100u

Repeat for -u 500 and -u 1000.
"""
from locust import HttpUser, task, between
import random

# Split queries into two pools:
# HIGH_REPEAT: queries that will be seen by many users → high cache hit rate
# LOW_REPEAT:  unique/novel queries → cache miss, measures real embedding latency
HIGH_REPEAT_QUERIES = [
    "What is the main objective of this project?",
    "Summarize the key findings.",
    "What technology stack is used?",
]
NOVEL_QUERIES = [
    "What is NexaShield?",
    "How does biodiversity relate to this document?",
    "Who authored the report?",
    "What are the financial highlights for Q3?",
    "Explain the methodology section.",
    "What risk factors are mentioned?",
    "Describe the infrastructure recommendations.",
]


class CachedQueryUser(HttpUser):
    """
    Models realistic traffic with query repetition patterns:
    - 60% repeated queries (should hit Redis cache after warmup)
    - 40% novel unique queries (cache miss, measures real embedding latency)
    """
    wait_time = between(1, 3)

    def on_start(self):
        self.client.get("/api/v1/health/metrics", name="/api/v1/health/metrics")

    @task(6)
    def repeated_query(self):
        """Simulates returning users asking the same questions → cache hits."""
        query = random.choice(HIGH_REPEAT_QUERIES)
        payload = {"query": query, "embedding_model": "minilm", "top_k": "5"}
        with self.client.post(
            "/api/v1/query", data=payload, name="/api/v1/query (Repeated/Cached)", catch_response=True
        ) as resp:
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                cache_hit = data.get("cache_hit", False)
                resp.success()
                # Tag response so we can see hit/miss ratio in Locust output
                if not cache_hit:
                    resp.name = "/api/v1/query (Repeated/MISS)"
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(4)
    def novel_query(self):
        """Simulates first-time users with unique queries → always cache misses."""
        query = random.choice(NOVEL_QUERIES)
        payload = {"query": query, "embedding_model": "minilm", "top_k": "5"}
        self.client.post("/api/v1/query", data=payload, name="/api/v1/query (Novel/Miss)")
