"""
embedding_benchmark.py — Day 2: Embedding Model Speed & Memory Benchmark
=========================================================================
Runs all 3 local embedding models on the same set of chunks
(extracted from test_pdfs/) and reports:
  - Embedding latency (ms/chunk)
  - Total time (seconds)
  - Peak memory (MB)
  - Dimensionality
  - Batched vs un-batched comparison

Usage:
    cd D:\\sia-utilities\\Week_4
    python embedding_benchmark.py
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.pdfparser import PDFParserService
from app.services.chunker import get_chunker
from app.services.embedder import get_embedder

TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")
MODELS = ["minilm", "bge", "e5"]
RESULTS = []


def collect_chunks():
    """Extract and chunk sample text to use as embedding input."""
    chunker = get_chunker("fixed", chunk_size=256, overlap=30)
    all_chunks = []
    for pdf in TEST_PDF_DIR.rglob("*.pdf"):
        try:
            doc = PDFParserService.extract_fast_text(str(pdf))
            chunks = chunker.chunk(doc)
            all_chunks.extend(chunks[:20])  # cap at 20 chunks per PDF
        except Exception:
            continue
    return all_chunks


def main():
    print("=" * 65)
    print("  Embedding Model Benchmark (Day 2)")
    print("=" * 65)

    print("\nCollecting chunks from test PDFs...")
    chunks = collect_chunks()
    if not chunks:
        print("No chunks collected — add PDFs to test_pdfs/")
        return

    texts = [c.text for c in chunks]
    print(f"Total chunks to embed: {len(texts)}\n")

    for model_key in MODELS:
        print(f"--- Model: {model_key} ---")
        try:
            embedder = get_embedder(model_key)

            # Batched benchmark
            batched = embedder.benchmark(texts, batch_size=32)
            batched["mode"] = "batched"
            RESULTS.append(batched)
            print(
                f"  [batched  ] dim={batched['dimensionality']:4d} "
                f"| {batched['ms_per_chunk']:6.2f} ms/chunk "
                f"| total={batched['total_time_sec']}s "
                f"| peak_mem={batched['peak_memory_mb']} MB"
            )

            # Un-batched benchmark (batch_size=1)
            unbatched = embedder.benchmark(texts[:20], batch_size=1)
            unbatched["mode"] = "unbatched"
            RESULTS.append(unbatched)
            print(
                f"  [unbatched] dim={unbatched['dimensionality']:4d} "
                f"| {unbatched['ms_per_chunk']:6.2f} ms/chunk "
                f"| total={unbatched['total_time_sec']}s "
                f"| peak_mem={unbatched['peak_memory_mb']} MB"
            )
        except Exception as e:
            print(f"  ERROR loading {model_key}: {e}")

    out = Path("embedding_benchmark_results.json")
    with open(out, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"\nBenchmark results saved to: {out.resolve()}")
    print("=" * 65)


if __name__ == "__main__":
    main()
