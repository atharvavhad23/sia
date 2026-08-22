"""
bench_utils.py — Shared utilities for all Week 5 benchmarks
"""

import json
import numpy as np
from pathlib import Path

VECTOR_DIM  = 384          # matches all-MiniLM-L6-v2
LANCEDB_DIR = Path(__file__).parent.parent / "lancedb_store"
RESULTS_DIR = Path(__file__).parent.parent / "results"


def make_synthetic_vectors(n: int, dim: int = VECTOR_DIM):
    """Generate n random L2-normalized vectors + dummy text metadata."""
    rng = np.random.default_rng(42)
    vecs = rng.standard_normal((n, dim)).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    vecs /= norms
    meta = [f"chunk text sample {i}" for i in range(n)]
    return vecs, meta


def get_db_path(bench_name: str) -> Path:
    p = LANCEDB_DIR / bench_name
    p.mkdir(parents=True, exist_ok=True)
    return p


def save_results(filename: str, data):
    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / filename
    with open(out, "w") as f:
        json.dump(data, f, indent=2)
    print(f"  -> Saved: {out.resolve()}")


def load_results(filename: str):
    path = RESULTS_DIR / filename
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return []
