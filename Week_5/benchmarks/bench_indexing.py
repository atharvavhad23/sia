"""
bench_indexing.py — Week 5: Indexing Strategy Comparison
=========================================================
Compares three configurations on a 10K-vector dataset:
  1. No index (brute-force flat scan)
  2. IVF_PQ  (num_partitions=256, num_sub_vectors=16)
  3. IVF_PQ Tuned (num_partitions=512, num_sub_vectors=32)

Metrics:
  - Index build time (seconds)
  - Query latency: p50 / p95 / p99 (ms, 100 queries)
  - Recall@10 vs brute-force ground truth

Output: results/indexing_results.json
"""

import sys, time, shutil
import numpy as np
import pyarrow as pa
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lancedb
from benchmarks.bench_utils import (
    make_synthetic_vectors, get_db_path, VECTOR_DIM, save_results
)

N_ROWS     = 10_000
N_QUERIES  = 100
TOP_K      = 10

STRATEGIES = [
    {"name": "No Index (Brute-Force)", "index": None},
    {"name": "IVF_PQ (default)",       "index": {"num_partitions": 256, "num_sub_vectors": 16}},
    {"name": "IVF_PQ (tuned)",         "index": {"num_partitions": 512, "num_sub_vectors": 32}},
]


def build_table(db_path, vectors, meta):
    db = lancedb.connect(str(db_path))
    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
        pa.field("id",     pa.string()),
        pa.field("text",   pa.string()),
    ])
    rows = [{"vector": v.tolist(), "id": str(i), "text": meta[i]}
            for i, v in enumerate(vectors)]
    tbl = db.create_table("indexing_bench", data=rows, schema=schema)
    return db, tbl


def get_ground_truth(tbl, queries, top_k):
    """Brute-force ground truth: exact top-k ids per query."""
    gt = []
    for q in queries:
        res = tbl.search(q.tolist()).limit(top_k).to_list()
        gt.append({r["id"] for r in res})
    return gt


def compute_recall(results_ids, gt_ids):
    if not gt_ids:
        return 0.0
    return len(results_ids & gt_ids) / len(gt_ids)


def bench_indexing():
    vectors, meta = make_synthetic_vectors(N_ROWS)
    rng = np.random.default_rng(99)
    query_vecs = rng.standard_normal((N_QUERIES, VECTOR_DIM)).astype(np.float32)
    query_vecs /= np.linalg.norm(query_vecs, axis=1, keepdims=True)

    # Brute-force ground truth first
    print("  Computing ground truth (brute-force)...")
    bf_path = get_db_path("index_bf")
    shutil.rmtree(bf_path, ignore_errors=True)
    _, bf_tbl = build_table(bf_path, vectors, meta)
    ground_truth = get_ground_truth(bf_tbl, query_vecs, TOP_K)

    results = []
    for strat in STRATEGIES:
        print(f"\n  [{strat['name']}]")
        db_path = get_db_path(f"index_{strat['name'].replace(' ','_')}")
        shutil.rmtree(db_path, ignore_errors=True)
        db, tbl = build_table(db_path, vectors, meta)

        # Build index
        build_time = 0.0
        if strat["index"]:
            t0 = time.perf_counter()
            tbl.create_index(
                metric="cosine",
                num_partitions=strat["index"]["num_partitions"],
                num_sub_vectors=strat["index"]["num_sub_vectors"],
            )
            build_time = round(time.perf_counter() - t0, 4)
            print(f"    Index built in {build_time}s")

        # Query latency
        latencies = []
        recalls = []
        for i, q in enumerate(query_vecs):
            t0 = time.perf_counter()
            res = tbl.search(q.tolist()).limit(TOP_K).to_list()
            latencies.append((time.perf_counter() - t0) * 1000)
            res_ids = {r["id"] for r in res}
            recalls.append(compute_recall(res_ids, ground_truth[i]))

        arr = np.array(latencies)
        row = {
            "strategy":       strat["name"],
            "build_time_sec": build_time,
            "p50_ms":         round(float(np.percentile(arr, 50)), 4),
            "p95_ms":         round(float(np.percentile(arr, 95)), 4),
            "p99_ms":         round(float(np.percentile(arr, 99)), 4),
            "recall_at_10":   round(float(np.mean(recalls)), 4),
        }
        results.append(row)
        print(f"    p50={row['p50_ms']}ms p99={row['p99_ms']}ms "
              f"recall@10={row['recall_at_10']:.3f}")

    save_results("indexing_results.json", results)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  Indexing Strategy Benchmark")
    print("=" * 60)
    bench_indexing()
