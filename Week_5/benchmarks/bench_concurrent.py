"""
bench_concurrent.py — Week 5: Concurrent Query Throughput
==========================================================
Simulates concurrent users hitting the LanceDB query endpoint.
Thread counts: 1, 2, 4, 8, 16
Each thread fires 50 queries on a shared 10K-vector table.

Metrics:
  - Total throughput (queries/sec)
  - p99 latency across all threads
  - Error rate (%)

Output: results/concurrent_results.json
"""

import sys, time, shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pyarrow as pa
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from benchmarks.bench_utils import (
    make_synthetic_vectors, get_db_path, VECTOR_DIM, save_results
)

N_ROWS        = 10_000
QUERIES_EACH  = 50
THREAD_COUNTS = [1, 2, 4, 8, 16]
TOP_K         = 5


def build_shared_table():
    vectors, meta = make_synthetic_vectors(N_ROWS)
    db_path = get_db_path("concurrent_bench")
    shutil.rmtree(db_path, ignore_errors=True)
    db = lancedb.connect(str(db_path))
    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
        pa.field("id",     pa.string()),
        pa.field("text",   pa.string()),
    ])
    rows = [{"vector": v.tolist(), "id": str(i), "text": meta[i]}
            for i, v in enumerate(vectors)]
    tbl = db.create_table("concurrent_bench", data=rows, schema=schema)
    tbl.create_index(metric="cosine", num_partitions=256, num_sub_vectors=16)
    return db_path


def worker(db_path, queries, top_k):
    """Single thread: opens its own connection and fires queries."""
    db  = lancedb.connect(str(db_path))
    tbl = db.open_table("concurrent_bench")
    latencies, errors = [], 0
    for q in queries:
        try:
            t0 = time.perf_counter()
            tbl.search(q.tolist()).nprobes(8).limit(top_k).to_list()
            latencies.append((time.perf_counter() - t0) * 1000)
        except Exception:
            errors += 1
    return latencies, errors


def bench_concurrent():
    print("  Building shared table...")
    db_path = build_shared_table()

    rng = np.random.default_rng(55)
    all_queries = rng.standard_normal((max(THREAD_COUNTS) * QUERIES_EACH, VECTOR_DIM)).astype(np.float32)
    all_queries /= np.linalg.norm(all_queries, axis=1, keepdims=True)

    results = []
    for n_threads in THREAD_COUNTS:
        # Split queries across threads
        thread_queries = [
            all_queries[t * QUERIES_EACH:(t + 1) * QUERIES_EACH]
            for t in range(n_threads)
        ]
        all_latencies, total_errors = [], 0
        start = time.perf_counter()

        with ThreadPoolExecutor(max_workers=n_threads) as pool:
            futures = [pool.submit(worker, db_path, tq, TOP_K)
                       for tq in thread_queries]
            for f in as_completed(futures):
                lats, errs = f.result()
                all_latencies.extend(lats)
                total_errors += errs

        elapsed = time.perf_counter() - start
        total_queries = n_threads * QUERIES_EACH - total_errors
        arr = np.array(all_latencies)

        row = {
            "threads":       n_threads,
            "total_queries": total_queries,
            "elapsed_sec":   round(elapsed, 4),
            "qps":           round(total_queries / elapsed, 2),
            "p50_ms":        round(float(np.percentile(arr, 50)), 4) if len(arr) else 0,
            "p99_ms":        round(float(np.percentile(arr, 99)), 4) if len(arr) else 0,
            "error_rate_pct": round(100 * total_errors / (n_threads * QUERIES_EACH), 2),
        }
        results.append(row)
        print(f"  threads={n_threads:>2} | {row['qps']:>7.1f} qps "
              f"| p99={row['p99_ms']:>7.2f}ms "
              f"| errors={row['error_rate_pct']}%")

    save_results("concurrent_results.json", results)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  Concurrent Query Benchmark")
    print("=" * 60)
    bench_concurrent()
