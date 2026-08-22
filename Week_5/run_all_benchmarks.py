"""
run_all_benchmarks.py — Week 5: Master Benchmark Runner
========================================================
Runs all 6 benchmarks in sequence and prints a final summary table.

Usage:
    cd D:\\sia-utilities\\Week_5
    python run_all_benchmarks.py
"""

import sys, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from benchmarks.bench_insertion  import bench_insertion
from benchmarks.bench_indexing   import bench_indexing
from benchmarks.bench_query      import bench_query
from benchmarks.bench_concurrent import bench_concurrent
from benchmarks.bench_storage    import bench_storage
from benchmarks.bench_stress     import bench_stress
from benchmarks.bench_utils      import RESULTS_DIR, save_results

SEP = "=" * 68


def section(title):
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def main():
    print(SEP)
    print("  WEEK 5 — LanceDB Full Benchmark Suite")
    print("  SIA PDF Extraction Microservice")
    print(SEP)

    overall_start = time.perf_counter()
    summary = {}

    section("1/6  Insertion Latency")
    ins = bench_insertion()
    summary["insertion"] = {
        "max_rows_per_sec": max(r["rows_per_sec"] for r in ins),
        "p99_at_50k":       next((r["p99_ms"] for r in ins if r["n_rows"] == 50_000), None),
    }

    section("2/6  Indexing Strategy Comparison")
    idx = bench_indexing()
    best_idx = max(idx, key=lambda r: r["recall_at_10"])
    summary["indexing"] = {
        "recommended": best_idx["strategy"],
        "recall_at_10": best_idx["recall_at_10"],
        "p50_ms": best_idx["p50_ms"],
    }

    section("3/6  Query Latency vs nprobe")
    qry = bench_query()
    # Sweet spot: best recall with p99 < 50ms
    sweet = next((r for r in sorted(qry, key=lambda x: x["recall_at_10"], reverse=True)
                  if r["p99_ms"] < 50), qry[-1])
    summary["query"] = {
        "sweet_spot_nprobe": sweet["nprobe"],
        "p50_ms": sweet["p50_ms"],
        "recall_at_10": sweet["recall_at_10"],
    }

    section("4/6  Concurrent Queries")
    con = bench_concurrent()
    peak = max(con, key=lambda r: r["qps"])
    summary["concurrent"] = {
        "peak_qps": peak["qps"],
        "peak_threads": peak["threads"],
        "p99_at_peak": peak["p99_ms"],
    }

    section("5/6  Storage Utilization")
    sto = bench_storage()
    summary["storage"] = {
        "ratio_at_10k": next((r["compression_ratio"] for r in sto if r["n_rows"] == 10_000), None),
        "bytes_per_vector": next((r["bytes_per_vector"] for r in sto if r["n_rows"] == 10_000), None),
    }

    section("6/6  Stress Test (60 seconds)")
    stress = bench_stress()
    summary["stress"] = {
        "avg_qps": stress["avg_qps"],
        "peak_p99_ms": stress["peak_p99_ms"],
        "peak_mem_mib": stress["peak_mem_mib"],
        "total_errors": stress["total_errors"],
    }

    total_time = round(time.perf_counter() - overall_start, 1)
    summary["total_benchmark_time_sec"] = total_time

    save_results("summary.json", summary)

    # Final summary table
    print(f"\n{SEP}")
    print("  FINAL SUMMARY")
    print(SEP)
    print(f"  Insertion         Peak {summary['insertion']['max_rows_per_sec']:.0f} rows/s | "
          f"p99@50K = {summary['insertion']['p99_at_50k']}ms")
    print(f"  Indexing          Best: {summary['indexing']['recommended']} | "
          f"recall@10 = {summary['indexing']['recall_at_10']}")
    print(f"  Query (nprobe)    Sweet spot nprobe={summary['query']['sweet_spot_nprobe']} | "
          f"recall@10={summary['query']['recall_at_10']}")
    print(f"  Concurrent        Peak {summary['concurrent']['peak_qps']} QPS @ "
          f"{summary['concurrent']['peak_threads']} threads")
    print(f"  Storage           {summary['storage']['bytes_per_vector']} bytes/vector | "
          f"{summary['storage']['ratio_at_10k']}x ratio")
    print(f"  Stress            {summary['stress']['avg_qps']} avg QPS | "
          f"peak p99={summary['stress']['peak_p99_ms']}ms | "
          f"errors={summary['stress']['total_errors']}")
    print(f"\n  Total runtime: {total_time}s")
    print(f"  Results in: {RESULTS_DIR.resolve()}")
    print(SEP)


if __name__ == "__main__":
    main()
