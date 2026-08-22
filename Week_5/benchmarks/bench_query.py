"""
bench_query.py — Week 5: Query Latency vs nprobe
=================================================
Fixed 10K vector dataset with IVF_PQ index.
Sweeps nprobe values: 1, 4, 8, 16, 32
Measures: p50 / p95 / p99 query latency + recall@10

Output: results/query_results.json
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

N_ROWS    = 10_000
N_QUERIES = 200
TOP_K     = 10
NPROBES   = [1, 4, 8, 16, 32]


def bench_query():
    vectors, meta = make_synthetic_vectors(N_ROWS)
    rng = np.random.default_rng(77)
    query_vecs = rng.standard_normal((N_QUERIES, VECTOR_DIM)).astype(np.float32)
    query_vecs /= np.linalg.norm(query_vecs, axis=1, keepdims=True)

    # Build table + IVF_PQ index once
    db_path = get_db_path("query_bench")
    shutil.rmtree(db_path, ignore_errors=True)
    db = lancedb.connect(str(db_path))
    schema = pa.schema([
        pa.field("vector", pa.list_(pa.float32(), VECTOR_DIM)),
        pa.field("id",     pa.string()),
        pa.field("text",   pa.string()),
    ])
    rows = [{"vector": v.tolist(), "id": str(i), "text": meta[i]}
            for i, v in enumerate(vectors)]
    tbl = db.create_table("query_bench", data=rows, schema=schema)
    tbl.create_index(metric="cosine", num_partitions=256, num_sub_vectors=16)

    # Ground truth (brute-force, nprobe not applicable here — use full scan)
    gt = []
    for q in query_vecs:
        res = tbl.search(q.tolist()).nprobes(N_ROWS).limit(TOP_K).to_list()
        gt.append({r["id"] for r in res})

    results = []
    for nprobe in NPROBES:
        latencies, recalls = [], []
        for i, q in enumerate(query_vecs):
            t0 = time.perf_counter()
            res = tbl.search(q.tolist()).nprobes(nprobe).limit(TOP_K).to_list()
            latencies.append((time.perf_counter() - t0) * 1000)
            res_ids = {r["id"] for r in res}
            hit = len(res_ids & gt[i]) / max(1, len(gt[i]))
            recalls.append(hit)

        arr = np.array(latencies)
        row = {
            "nprobe":       nprobe,
            "p50_ms":       round(float(np.percentile(arr, 50)), 4),
            "p95_ms":       round(float(np.percentile(arr, 95)), 4),
            "p99_ms":       round(float(np.percentile(arr, 99)), 4),
            "recall_at_10": round(float(np.mean(recalls)), 4),
        }
        results.append(row)
        print(f"  nprobe={nprobe:>2} | p50={row['p50_ms']:>7.3f}ms "
              f"| p99={row['p99_ms']:>7.3f}ms "
              f"| recall@10={row['recall_at_10']:.4f}")

    save_results("query_results.json", results)
    return results


if __name__ == "__main__":
    print("=" * 60)
    print("  Query Latency vs nprobe Benchmark")
    print("=" * 60)
    bench_query()
