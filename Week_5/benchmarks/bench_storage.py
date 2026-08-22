"""
bench_storage.py — Week 5: Storage Utilization
===============================================
Measures disk usage of LanceDB .lance files at varying dataset sizes.
Compares raw float32 vector size vs actual storage.

Dataset sizes: 1K, 5K, 10K, 50K rows
Metrics:
  - Raw vector size (MB): n * dim * 4 bytes
  - LanceDB file size (MB): actual .lance directory size
  - Compression ratio: raw / actual
  - Storage per vector (KB)

Output: results/storage_results.json
"""

import sys, shutil
import numpy as np
import pyarrow as pa
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from benchmarks.bench_utils import (
    make_synthetic_vectors, get_db_path, VECTOR_DIM, save_results
)

SIZES = [1_000, 5_000, 10_000, 50_000]


def dir_size_mb(path: Path) -> float:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / (1024 ** 2), 4)


def bench_storage():
    results = []

    for n in SIZES:
        vectors, meta = make_synthetic_vectors(n)
        db_path = get_db_path(f"storage_{n}")
        shutil.rmtree(db_path, ignore_errors=True)

        db = lancedb.connect(str(db_path))
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
            pa.field("id",     pa.string()),
            pa.field("text",   pa.string()),
        ])
        rows = [{"vector": v.tolist(), "id": str(i), "text": meta[i]}
                for i, v in enumerate(vectors)]
        db.create_table("storage_bench", data=rows, schema=schema)

        raw_mb   = round(n * VECTOR_DIM * 4 / (1024 ** 2), 4)
        store_mb = dir_size_mb(db_path)
        ratio    = round(raw_mb / store_mb, 3) if store_mb > 0 else 0
        per_vec_kb = round(store_mb * 1024 / n, 4)

        row = {
            "n_rows":            n,
            "raw_size_mb":       raw_mb,
            "lancedb_size_mb":   store_mb,
            "compression_ratio": ratio,
            "bytes_per_vector":  round(store_mb * 1024 * 1024 / n, 2),
        }
        results.append(row)
        print(f"  n={n:>6} | raw={raw_mb:>7.2f}MB "
              f"| lance={store_mb:>7.2f}MB "
              f"| ratio={ratio:.3f}x "
              f"| {row['bytes_per_vector']:.1f} bytes/vec")

    save_results("storage_results.json", results)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  Storage Utilization Benchmark")
    print("=" * 60)
    bench_storage()
