"""
cache.py — Week 8: Redis Query Result Cache
============================================
Implements targeted caching for the query path, which Week 7 profiling
identified as the primary bottleneck at scale.

WHAT WE CACHE AND WHY:
  - Full query results (embedding → search → extractive QA output)
  - Cache key = SHA-256 of (normalized_query_text + embedding_model + top_k)
  - NOT caching individual embeddings — the sentence-transformers model
    already has an internal embedding cache per-process.

WHAT WE DON'T CACHE:
  - Ingestion results (these are unique per document, cache hit rate ≈ 0%)
  - Embedding vectors alone (LanceDB reads are already sub-2ms per Week 7)

INVALIDATION STRATEGY:
  - TTL-based: each cached result expires after REDIS_CACHE_TTL_SECONDS.
    Default is 3600s (1 hour). This prevents stale answers after re-ingestion.
  - Explicit purge: ingest_document() calls cache.invalidate_all() after a
    successful ingest, so fresh document uploads always flush stale answers.
    This is conservative but safe for a single-tenant service.

CACHE KEY DESIGN:
  key = f"sia:query:{sha256(f'{normalized_query}|{model}|{top_k}')}"
  - Normalized = lowercased + stripped + whitespace-collapsed to prevent
    identical queries from missing the cache due to whitespace differences.

MEASURABILITY:
  - Every response includes 'cache_hit': True/False so hit vs miss latency
    can be tracked independently (see Cache_Benchmark_Report.md).
"""

import hashlib
import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("sia.cache")
logger.setLevel(logging.INFO)

# ─────────────────────────────────────────────
# Configuration (from environment / defaults)
# ─────────────────────────────────────────────
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
REDIS_CACHE_TTL_SECONDS = int(os.getenv("REDIS_CACHE_TTL_SECONDS", "3600"))
REDIS_ENABLED = os.getenv("REDIS_ENABLED", "true").lower() == "true"


class RedisCache:
    """
    Thread-safe wrapper around Redis for caching query results.
    Falls back to a no-op if Redis is unavailable, ensuring the
    main pipeline is never blocked by cache failures.
    """

    def __init__(self):
        self._client = None
        self._available = False
        if REDIS_ENABLED:
            self._connect()

    def _connect(self):
        try:
            import redis
            self._client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                socket_connect_timeout=1,
                decode_responses=True,
            )
            self._client.ping()
            self._available = True
            logger.info(f"Redis cache connected at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            self._available = False
            logger.warning(f"Redis unavailable, caching disabled: {e}")

    @staticmethod
    def _build_key(query_text: str, embedding_model: str, top_k: int) -> str:
        """
        Build a deterministic cache key from query parameters.
        Normalizes query to avoid whitespace-induced cache misses.
        """
        normalized = " ".join(query_text.lower().strip().split())
        raw = f"{normalized}|{embedding_model}|{top_k}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"sia:query:{digest}"

    def get(self, query_text: str, embedding_model: str, top_k: int) -> Optional[Dict[str, Any]]:
        """Retrieve a cached result. Returns None on miss or Redis unavailability."""
        if not self._available:
            return None
        try:
            key = self._build_key(query_text, embedding_model, top_k)
            raw = self._client.get(key)
            if raw:
                logger.info(f"Cache HIT for key={key[:20]}...")
                return json.loads(raw)
            logger.info(f"Cache MISS for key={key[:20]}...")
            return None
        except Exception as e:
            logger.warning(f"Cache GET failed: {e}")
            return None

    def set(self, query_text: str, embedding_model: str, top_k: int, value: Dict[str, Any]) -> None:
        """Store a result. Silently skips on Redis unavailability."""
        if not self._available:
            return
        try:
            key = self._build_key(query_text, embedding_model, top_k)
            self._client.setex(key, REDIS_CACHE_TTL_SECONDS, json.dumps(value))
            logger.info(f"Cache SET for key={key[:20]}... TTL={REDIS_CACHE_TTL_SECONDS}s")
        except Exception as e:
            logger.warning(f"Cache SET failed: {e}")

    def invalidate_all(self) -> int:
        """
        Delete all SIA query cache entries.
        Called after a successful document ingest to prevent stale results.
        Returns the number of keys deleted.
        """
        if not self._available:
            return 0
        try:
            keys = self._client.keys("sia:query:*")
            if keys:
                deleted = self._client.delete(*keys)
                logger.info(f"Cache invalidated: {deleted} keys purged after new ingest.")
                return deleted
            return 0
        except Exception as e:
            logger.warning(f"Cache invalidation failed: {e}")
            return 0

    @property
    def is_available(self) -> bool:
        return self._available


# ─────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────
_cache: Optional[RedisCache] = None


def get_cache() -> RedisCache:
    global _cache
    if _cache is None:
        _cache = RedisCache()
    return _cache
