"""
throughput_benchmark.py — Day 3: End-to-End Throughput Measurement
====================================================================
Measures the full pipeline (extract → chunk → embed → store) for a
scoped matrix of chunking strategies × embedding models.

Matrix tested (compute-constrained scope):
  Strategies : fixed, recursive, layout_aware  (semantic skipped — too slow for batch)
  Models     : minilm, bge                     (e5 skipped — 768-dim doubles memory)

To include e5 or semantic, set INCLUDE_E5=True / INCLUDE_SEMANTIC=True below.

Metrics per combination:
  - Documents / minute
  - Chunks / second
  - Embedding throughput (chunks/sec)
  - End-to-end latency (seconds)
  - Peak memory (MiB)

Usage:
    cd D:\\sia-utilities\\Week_4
    python throughput_benchmark.py
"""

import sys
import json
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdfparser import PDFParserService
from app.services.chunker import get_chunker
from app.services.embedder import get_embedder

TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")

STRATEGIES = ["fixed", "recursive", "layout_aware"]
MODELS = ["minilm", "bge"]
INCLUDE_E5 = False        # flip to True to add e5 768-dim model
INCLUDE_SEMANTIC = False  # flip to True to add semantic chunker

if INCLUDE_E5:
    MODELS.append("e5")
if INCLUDE_SEMANTIC:
    STRATEGIES.append("semantic")

RESULTS = []


def run_pipeline_once(pdf_path: str, strategy: str, model_key: str) -> dict:
    tracemalloc.start()
    start = time.time()

    # Extract
    doc = PDFParserService.extract_fast_text(pdf_path)

    # Chunk
    chunker = get_chunker(strategy)
    chunks = chunker.chunk(doc)

    if not chunks:
        tracemalloc.stop()
        return {"chunks": 0, "skipped": True}

    # Embed
    embedder = get_embedder(model_key)
    texts = [c.text for c in chunks]
    t_embed_start = time.time()
    embedder.embed(texts, batch_size=32)
    embed_time = time.time() - t_embed_start

    total_time = time.time() - start
    _, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "chunks": len(chunks),
        "total_time_sec": round(total_time, 4),
        "embed_time_sec": round(embed_time, 4),
        "chunks_per_sec": round(len(chunks) / total_time, 2) if total_time > 0 else 0,
        "embed_chunks_per_sec": round(len(chunks) / embed_time, 2) if embed_time > 0 else 0,
        "peak_mem_mib": round(peak_mem / (1024 ** 2), 2),
        "skipped": False,
    }


def main():
    print("=" * 72)
    print("  Day 3 — Throughput Benchmark (Strategy × Model Matrix)")
    print("=" * 72)

    pdf_files = list(TEST_PDF_DIR.rglob("*.pdf"))
    if not pdf_files:
        print("No PDFs found. Add PDFs to test_pdfs/")
        return

    print(f"\nPDFs found: {len(pdf_files)}")
    print(f"Strategies: {STRATEGIES}")
    print(f"Models    : {MODELS}\n")

    for strategy in STRATEGIES:
        for model_key in MODELS:
            print(f"\n--- {strategy:15s} × {model_key:7s} ---")
            doc_times = []
            total_chunks = 0

            for pdf_path in pdf_files:
                try:
                    r = run_pipeline_once(str(pdf_path), strategy, model_key)
                    if r.get("skipped"):
                        print(f"  [SKIP] {pdf_path.name} — no chunks produced")
                        continue
                    doc_times.append(r["total_time_sec"])
                    total_chunks += r["chunks"]
                    print(
                        f"  {pdf_path.name:30s} | {r['chunks']:4d} chunks "
                        f"| {r['total_time_sec']}s "
                        f"| {r['embed_chunks_per_sec']} emb-chunks/s "
                        f"| mem={r['peak_mem_mib']} MiB"
                    )
                except Exception as e:
                    print(f"  [ERROR] {pdf_path.name}: {e}")

            if doc_times:
                total_elapsed = sum(doc_times)
                docs_per_min = round(60 * len(doc_times) / total_elapsed, 2) if total_elapsed else 0
                summary = {
                    "strategy": strategy,
                    "model": model_key,
                    "docs_processed": len(doc_times),
                    "total_chunks": total_chunks,
                    "avg_latency_sec": round(sum(doc_times) / len(doc_times), 4),
                    "docs_per_minute": docs_per_min,
                    "chunks_total": total_chunks,
                }
                RESULTS.append(summary)
                print(
                    f"  >> SUMMARY: {len(doc_times)} docs | "
                    f"{total_chunks} chunks | {docs_per_min} docs/min"
                )

    out = Path("throughput_results.json")
    with open(out, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nThroughput results saved to: {out.resolve()}")
    print("=" * 72)


if __name__ == "__main__":
    main()
