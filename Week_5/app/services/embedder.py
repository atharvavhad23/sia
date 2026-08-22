"""
embedder.py — Day 2: Embedding Model Module
============================================
Implements 3 embedding models behind a common BaseEmbedder interface:

  Model 1: all-MiniLM-L6-v2   — fast, 384-dim, great general purpose
  Model 2: bge-small-en-v1.5  — higher quality, 384-dim, BAAI open model
  Model 3: e5-base-v2          — 768-dim, strong at passage retrieval tasks

All models run locally via sentence-transformers (no API keys required).

Usage:
    from app.services.embedder import get_embedder

    embedder = get_embedder("minilm")
    vectors = embedder.embed(["chunk 1 text", "chunk 2 text"])
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import List

import numpy as np

logger = logging.getLogger("sia.embedder")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","name":"%(name)s"}'
    ))
    logger.addHandler(handler)
logger.propagate = False


# ─────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────
class BaseEmbedder(ABC):
    model_name: str = ""
    dimensionality: int = 0

    @abstractmethod
    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        """
        Args:
            texts:      list of strings to embed
            batch_size: number of texts processed per forward pass
        Returns:
            np.ndarray of shape (len(texts), dimensionality)
        """
        ...

    def embed_query(self, query: str) -> np.ndarray:
        """Convenience method: embed a single query string."""
        return self.embed([query])[0]

    def benchmark(self, texts: List[str], batch_size: int = 32) -> dict:
        """
        Runs embed() and returns latency + memory stats.
        Useful for the Day 2 benchmark comparison.
        """
        import tracemalloc
        tracemalloc.start()
        start = time.time()
        vectors = self.embed(texts, batch_size=batch_size)
        elapsed = time.time() - start
        _, peak_mem = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        n = len(texts)
        return {
            "model": self.model_name,
            "dimensionality": self.dimensionality,
            "num_chunks": n,
            "total_time_sec": round(elapsed, 4),
            "ms_per_chunk": round(1000 * elapsed / n, 3) if n else 0,
            "peak_memory_mb": round(peak_mem / (1024 ** 2), 2),
            "batch_size": batch_size,
        }


# ─────────────────────────────────────────────
# Model 1: all-MiniLM-L6-v2
# ─────────────────────────────────────────────
class MiniLMEmbedder(BaseEmbedder):
    """
    all-MiniLM-L6-v2: 384-dim, ~80MB model, extremely fast.
    Best for high-throughput pipelines where speed > quality.
    """
    model_name = "all-MiniLM-L6-v2"
    dimensionality = 384

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.array([])
        logger.info(f"MiniLMEmbedder: embedding {len(texts)} chunks (batch={batch_size})")
        return self._model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )


# ─────────────────────────────────────────────
# Model 2: bge-small-en-v1.5
# ─────────────────────────────────────────────
class BGESmallEmbedder(BaseEmbedder):
    """
    bge-small-en-v1.5: 384-dim BAAI model, higher quality than MiniLM.
    Optimized for retrieval tasks with instruction-style prefix support.
    """
    model_name = "BAAI/bge-small-en-v1.5"
    dimensionality = 384

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: List[str], batch_size: int = 32) -> np.ndarray:
        if not texts:
            return np.array([])
        # BGE models benefit from a passage prefix during indexing
        prefixed = [f"Represent this sentence: {t}" for t in texts]
        logger.info(f"BGESmallEmbedder: embedding {len(texts)} chunks (batch={batch_size})")
        return self._model.encode(
            prefixed,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def embed_query(self, query: str) -> np.ndarray:
        """BGE uses a different prefix for queries vs passages."""
        prefixed = f"Represent this question for searching: {query}"
        return self._model.encode(
            [prefixed],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]


# ─────────────────────────────────────────────
# Model 3: e5-base-v2
# ─────────────────────────────────────────────
class E5BaseEmbedder(BaseEmbedder):
    """
    intfloat/e5-base-v2: 768-dim, strong passage-retrieval quality.
    Higher memory cost (~200MB) but superior recall on diverse topics.
    """
    model_name = "intfloat/e5-base-v2"
    dimensionality = 768

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading model: {self.model_name}")
        self._model = SentenceTransformer(self.model_name)

    def embed(self, texts: List[str], batch_size: int = 16) -> np.ndarray:
        if not texts:
            return np.array([])
        prefixed = [f"passage: {t}" for t in texts]
        logger.info(f"E5BaseEmbedder: embedding {len(texts)} chunks (batch={batch_size})")
        return self._model.encode(
            prefixed,
            batch_size=batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

    def embed_query(self, query: str) -> np.ndarray:
        prefixed = f"query: {query}"
        return self._model.encode(
            [prefixed],
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )[0]


# ─────────────────────────────────────────────
# Factory helper
# ─────────────────────────────────────────────
def get_embedder(model_key: str) -> BaseEmbedder:
    """
    Factory: returns the correct embedder given a short key.
    Valid values: 'minilm', 'bge', 'e5'
    """
    MAP = {
        "minilm": MiniLMEmbedder,
        "bge": BGESmallEmbedder,
        "e5": E5BaseEmbedder,
    }
    if model_key not in MAP:
        raise ValueError(f"Unknown embedding model '{model_key}'. Choose from: {list(MAP)}")
    return MAP[model_key]()
