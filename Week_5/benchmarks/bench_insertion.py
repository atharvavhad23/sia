"""
bench_insertion.py — Week 5: Insertion Latency Benchmark
=========================================================
Measures how fast LanceDB can ingest batches of vectors at
varying dataset sizes: 100, 500, 1K, 5K, 10K, 50K rows.

Metrics collected per batch size:
  - Total insertion time (seconds)
  - Rows per second
  - p50 / p95 / p99 latency (per individual row)

Output: results/insertion_results.json
"""

import sys, json, time, shutil
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from benchmarks.bench_utils import (
    make_synthetic_vectors, get_db_path, VECTOR_DIM, save_results
)

BATCH_SIZES = [100, 500, 1_000, 5_000, 10_000, 50_000]
TABLE_NAME  = "insertion_bench"


def bench_insertion() -> list[dict]:
    results = []

    for n in BATCH_SIZES:
        db_path = get_db_path("insertion")
        shutil.rmtree(db_path, ignore_errors=True)
        db = lancedb.connect(str(db_path))

        vectors, meta = make_synthetic_vectors(n)
        rows = [
            {"vector": v.tolist(), "id": str(i), "text": meta[i]}
            for i, v in enumerate(vectors)
        ]

        # Time individual row insertions in chunks for p-latency
        chunk = 50
        row_times = []
        tbl = None
        total_start = time.perf_counter()

        for start in range(0, n, chunk):
            batch = rows[start:start + chunk]
            t0 = time.perf_counter()
            if tbl is None:
                import pyarrow as pa
                schema = pa.schema([
                    pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
                    pa.field("id",     pa.string()),
                    pa.field("text",   pa.string()),
                ])
                tbl = db.create_table(TABLE_NAME, data=batch, schema=schema)
            else:
                tbl.add(batch)
            elapsed = time.perf_counter() - t0
            row_times.append(elapsed / len(batch))

        total_time = time.perf_counter() - total_start

        arr = np.array(row_times) * 1000  # ms per row
        result = {
            "n_rows":        n,
            "total_time_sec": round(total_time, 4),
            "rows_per_sec":  round(n / total_time, 2),
            "p50_ms":        round(float(np.percentile(arr, 50)), 4),
            "p95_ms":        round(float(np.percentile(arr, 95)), 4),
            "p99_ms":        round(float(np.percentile(arr, 99)), 4),
        }
        results.append(result)
        print(f"  n={n:>6} | {result['rows_per_sec']:>8.1f} rows/s "
              f"| p50={result['p50_ms']:.3f}ms "
              f"| p99={result['p99_ms']:.3f}ms "
              f"| total={result['total_time_sec']}s")

    save_results("insertion_results.json", results)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  Insertion Latency Benchmark")
    print("=" * 60)
    bench_insertion()
