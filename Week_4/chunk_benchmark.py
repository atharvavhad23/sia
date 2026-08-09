"""
chunk_benchmark.py — Day 1: Chunking Strategy Benchmark
=========================================================
Runs all four chunking strategies over every PDF in test_pdfs/
and reports per-strategy stats:
  - Chunk count
  - Average / Median chunk size (tokens)
  - Size variance (std dev)
  - Boundary-violation rate (% of chunks < 10 tokens = bad split)
  - Wall-clock time (seconds)

Usage:
    cd D:\\sia-utilities\\Week_4
    python chunk_benchmark.py
"""

import time
import statistics
import json
from pathlib import Path

# Make sure app package is importable from Week_4 root
import sys
sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdfparser import PDFParserService
from app.services.chunker import get_chunker

TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")
STRATEGIES = ["fixed", "recursive", "layout_aware"]  # semantic added separately (needs model load)
RESULTS = []


def benchmark_strategy(strategy: str, pages_data: dict, filename: str) -> dict:
    chunker = get_chunker(strategy)
    start = time.time()
    try:
        chunks = chunker.chunk(pages_data)
    except Exception as e:
        return {"strategy": strategy, "file": filename, "error": str(e)}
    elapsed = round(time.time() - start, 4)

    if not chunks:
        return {
            "strategy": strategy, "file": filename,
            "chunk_count": 0, "avg_tokens": 0, "median_tokens": 0,
            "std_dev": 0, "boundary_violation_rate_pct": 0, "time_sec": elapsed
        }

    token_counts = [c.token_count for c in chunks]
    bad = sum(1 for t in token_counts if t < 10)   # < 10 tokens = boundary violation

    return {
        "strategy": strategy,
        "file": filename,
        "chunk_count": len(chunks),
        "avg_tokens": round(statistics.mean(token_counts), 2),
        "median_tokens": statistics.median(token_counts),
        "std_dev": round(statistics.pstdev(token_counts), 2),
        "boundary_violation_rate_pct": round(100 * bad / len(chunks), 2),
        "time_sec": elapsed,
    }


def main():
    print("=" * 65)
    print("  Chunking Strategy Benchmark")
    print("=" * 65)

    pdf_files = list(TEST_PDF_DIR.rglob("*.pdf"))
    if not pdf_files:
        print(f"No PDFs found in {TEST_PDF_DIR}")
        return

    for pdf in pdf_files:
        print(f"\nParsing: {pdf.name}")
        try:
            doc = PDFParserService.extract_fast_text(str(pdf))
        except Exception as e:
            print(f"  [SKIP] Extraction failed: {e}")
            continue

        for strategy in STRATEGIES:
            result = benchmark_strategy(strategy, doc, pdf.name)
            RESULTS.append(result)
            if "error" in result:
                print(f"  [{strategy:14s}] ERROR: {result['error']}")
            else:
                print(
                    f"  [{strategy:14s}] chunks={result['chunk_count']:4d} "
                    f"| avg={result['avg_tokens']:6.1f}tok "
                    f"| median={result['median_tokens']:6.1f}tok "
                    f"| std={result['std_dev']:5.1f} "
                    f"| violations={result['boundary_violation_rate_pct']:4.1f}% "
                    f"| {result['time_sec']}s"
                )

    # Try semantic (loads model once)
    print("\nRunning semantic strategy (loads embedding model — may take a moment)...")
    try:
        sem_chunker = get_chunker("semantic")
        for pdf in pdf_files:
            try:
                doc = PDFParserService.extract_fast_text(str(pdf))
                result = benchmark_strategy.__wrapped__ if hasattr(benchmark_strategy, '__wrapped__') else None
                start = time.time()
                chunks = sem_chunker.chunk(doc)
                elapsed = round(time.time() - start, 4)
                if chunks:
                    token_counts = [c.token_count for c in chunks]
                    bad = sum(1 for t in token_counts if t < 10)
                    result = {
                        "strategy": "semantic",
                        "file": pdf.name,
                        "chunk_count": len(chunks),
                        "avg_tokens": round(statistics.mean(token_counts), 2),
                        "median_tokens": statistics.median(token_counts),
                        "std_dev": round(statistics.pstdev(token_counts), 2),
                        "boundary_violation_rate_pct": round(100 * bad / len(chunks), 2),
                        "time_sec": elapsed,
                    }
                    RESULTS.append(result)
                    print(
                        f"  [semantic       ] chunks={result['chunk_count']:4d} "
                        f"| avg={result['avg_tokens']:6.1f}tok "
                        f"| {result['time_sec']}s ({pdf.name})"
                    )
            except Exception as e:
                print(f"  [semantic] {pdf.name}: {e}")
    except Exception as e:
        print(f"  Semantic strategy failed: {e}")

    # Save raw results
    out_file = Path("chunk_benchmark_results.json")
    with open(out_file, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nRaw benchmark data saved to: {out_file.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    main()
