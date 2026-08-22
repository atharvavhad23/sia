"""
bench_stress.py — Week 5: Stress Test Retrieval
================================================
Sustained 60-second query load at 4 concurrent threads.
Measures system behaviour under prolonged high-load conditions.

Metrics (captured in 10-second windows):
  - Queries per second (per window)
  - p99 latency per window
  - Memory usage (MiB, via psutil)
  - Total error count

Output: results/stress_results.json
"""

import sys, time, shutil, threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pyarrow as pa
import psutil, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from benchmarks.bench_utils import (
    make_synthetic_vectors, get_db_path, VECTOR_DIM, save_results
)

N_ROWS       = 10_000
DURATION_SEC = 60
THREADS      = 4
WINDOW_SEC   = 10
TOP_K        = 5


def build_stress_table():
    vectors, meta = make_synthetic_vectors(N_ROWS)
    db_path = get_db_path("stress_bench")
    shutil.rmtree(db_path, ignore_errors=True)
    db = lancedb.connect(str(db_path))
    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
        pa.field("id",     pa.string()),
        pa.field("text",   pa.string()),
    ])
    rows = [{"vector": v.tolist(), "id": str(i), "text": meta[i]}
            for i, v in enumerate(vectors)]
    tbl = db.create_table("stress_bench", data=rows, schema=schema)
    tbl.create_index(metric="cosine", num_partitions=256, num_sub_vectors=16)
    return db_path


def stress_worker(db_path, stop_event, results_lock, all_latencies, errors):
    rng = np.random.default_rng()
    db  = lancedb.connect(str(db_path))
    tbl = db.open_table("stress_bench")
    while not stop_event.is_set():
        q = rng.standard_normal(VECTOR_DIM).astype(np.float32)
        q /= np.linalg.norm(q)
        try:
            t0 = time.perf_counter()
            tbl.search(q.tolist()).nprobes(8).limit(TOP_K).to_list()
            lat = (time.perf_counter() - t0) * 1000
            with results_lock:
                all_latencies.append((time.perf_counter(), lat))
        except Exception:
            with results_lock:
                errors[0] += 1


def bench_stress():
    print("  Building stress table...")
    db_path = build_stress_table()

    all_latencies = []   # (timestamp, latency_ms)
    errors        = [0]
    results_lock  = threading.Lock()
    stop_event    = threading.Event()
    proc          = psutil.Process(os.getpid())

    print(f"  Running {DURATION_SEC}s stress test at {THREADS} threads...")
    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        futures = [
            pool.submit(stress_worker, db_path, stop_event, results_lock, all_latencies, errors)
            for _ in range(THREADS)
        ]
        start_time = time.perf_counter()
        windows = []
        prev_window_end = start_time

        while time.perf_counter() - start_time < DURATION_SEC:
            time.sleep(WINDOW_SEC)
            now = time.perf_counter()
            mem_mb = proc.memory_info().rss / (1024 ** 2)

            with results_lock:
                window_lats = [
                    lat for ts, lat in all_latencies
                    if prev_window_end <= ts < now
                ]

            window_sec = round(now - start_time, 1)
            if window_lats:
                arr = np.array(window_lats)
                w = {
                    "elapsed_sec": window_sec,
                    "qps":         round(len(window_lats) / WINDOW_SEC, 2),
                    "p50_ms":      round(float(np.percentile(arr, 50)), 3),
                    "p99_ms":      round(float(np.percentile(arr, 99)), 3),
                    "mem_mib":     round(mem_mb, 2),
                    "error_count": errors[0],
                }
            else:
                w = {"elapsed_sec": window_sec, "qps": 0, "p50_ms": 0,
                     "p99_ms": 0, "mem_mib": round(mem_mb, 2), "error_count": errors[0]}
            windows.append(w)
            prev_window_end = now
            print(f"  t={window_sec:>5}s | {w['qps']:>6.1f} qps "
                  f"| p99={w['p99_ms']:>6.2f}ms | mem={w['mem_mib']}MiB")

        stop_event.set()

    summary = {
        "duration_sec": DURATION_SEC,
        "threads":      THREADS,
        "total_queries": len(all_latencies),
        "total_errors":  errors[0],
        "avg_qps":       round(len(all_latencies) / DURATION_SEC, 2),
        "peak_p99_ms":   round(max(w["p99_ms"] for w in windows), 3),
        "peak_mem_mib":  round(max(w["mem_mib"] for w in windows), 2),
        "windows":       windows,
    }
    save_results("stress_results.json", summary)
    print(f"\n  Total queries: {summary['total_queries']} | "
          f"Avg QPS: {summary['avg_qps']} | Peak p99: {summary['peak_p99_ms']}ms")
    return summary


if __name__ == "__main__":
    print("=" * 60)
    print("  Stress Test Retrieval")
    print("=" * 60)
    bench_stress()
