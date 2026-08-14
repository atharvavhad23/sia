"""
retrieval_eval.py — Day 4: Retrieval Quality Evaluation
=========================================================
Builds a labeled eval set of 15 queries and computes IR metrics:
  - Precision@k  (k = 3, 5, 10)
  - Recall@k     (k = 3, 5, 10)
  - MRR          (Mean Reciprocal Rank)
  - NDCG@k       (k = 3, 5, 10)

The eval set uses text that WILL be in the ingested PDFs so that
ground-truth chunks can be identified by keyword matching.

Usage:
    cd D:\\sia-utilities\\Week_4
    # First ingest at least one PDF:
    #   POST /api/v1/ingest  OR run ingest_for_eval() below
    python retrieval_eval.py
"""

import sys
import json
import math
import time
from pathlib import Path
from typing import List, Dict, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))


# ─────────────────────────────────────────────
# Labeled eval set — 15 queries
# Each entry: {query, keywords} where keywords are strings that
# MUST appear in a chunk for it to count as a "relevant" result.
# ─────────────────────────────────────────────
EVAL_SET = [
    {"id": "Q01", "query": "What is the total revenue reported?",
     "keywords": ["revenue", "total revenue", "net revenue"]},

    {"id": "Q02", "query": "What are the key financial highlights?",
     "keywords": ["financial highlights", "highlights", "financial performance"]},

    {"id": "Q03", "query": "What is the gross profit margin?",
     "keywords": ["gross profit", "profit margin", "gross margin"]},

    {"id": "Q04", "query": "What legal obligations are mentioned?",
     "keywords": ["obligation", "liability", "legal", "clause"]},

    {"id": "Q05", "query": "What are the terms and conditions?",
     "keywords": ["terms", "conditions", "agreement", "contract"]},

    {"id": "Q06", "query": "Who are the parties involved in the contract?",
     "keywords": ["party", "parties", "agreement between", "contractor"]},

    {"id": "Q07", "query": "What is the research methodology?",
     "keywords": ["methodology", "method", "approach", "research design"]},

    {"id": "Q08", "query": "What are the conclusions of the study?",
     "keywords": ["conclusion", "findings", "result", "summary"]},

    {"id": "Q09", "query": "What is the invoice total amount?",
     "keywords": ["total", "amount due", "invoice", "subtotal"]},

    {"id": "Q10", "query": "What items are listed on the invoice?",
     "keywords": ["item", "description", "quantity", "unit price"]},

    {"id": "Q11", "query": "What is the operating expense breakdown?",
     "keywords": ["operating expense", "expense", "cost", "opex"]},

    {"id": "Q12", "query": "What are the risks mentioned in the document?",
     "keywords": ["risk", "risks", "uncertainty", "mitigation"]},

    {"id": "Q13", "query": "What is the payment schedule or due date?",
     "keywords": ["payment", "due date", "schedule", "deadline"]},

    {"id": "Q14", "query": "What is the scope of work defined?",
     "keywords": ["scope", "scope of work", "deliverable", "objective"]},

    {"id": "Q15", "query": "What tables contain numerical data?",
     "keywords": ["table", "figure", "data", "percentage", "%"]},
]


# ─────────────────────────────────────────────
# IR metric helpers
# ─────────────────────────────────────────────

def is_relevant(chunk_text: str, keywords: List[str]) -> bool:
    text_lower = chunk_text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def precision_at_k(retrieved: List[bool], k: int) -> float:
    top_k = retrieved[:k]
    return sum(top_k) / k if k > 0 else 0.0


def recall_at_k(retrieved: List[bool], total_relevant: int, k: int) -> float:
    if total_relevant == 0:
        return 0.0
    return sum(retrieved[:k]) / total_relevant


def reciprocal_rank(retrieved: List[bool]) -> float:
    for i, rel in enumerate(retrieved):
        if rel:
            return 1.0 / (i + 1)
    return 0.0


def ndcg_at_k(retrieved: List[bool], k: int) -> float:
    def dcg(rels, k):
        return sum(rel / math.log2(i + 2) for i, rel in enumerate(rels[:k]))
    ideal = sorted(retrieved, reverse=True)
    idcg = dcg(ideal, k)
    return dcg(retrieved, k) / idcg if idcg > 0 else 0.0


# ─────────────────────────────────────────────
# Optional: ingest test PDFs before eval
# ─────────────────────────────────────────────
def ingest_for_eval(strategy: str, model_key: str):
    from app.services.rag_pipeline import ingest_document
    TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")
    for pdf in TEST_PDF_DIR.rglob("*.pdf"):
        try:
            print(f"  Ingesting {pdf.name} [{strategy}/{model_key}]...")
            ingest_document(str(pdf), pdf.name, strategy, model_key, "fast")
        except Exception as e:
            print(f"  [SKIP] {pdf.name}: {e}")


# ─────────────────────────────────────────────
# Main evaluation loop
# ─────────────────────────────────────────────
def evaluate(strategy: str, model_key: str, top_k_values: List[int] = [3, 5, 10]) -> Dict[str, Any]:
    from app.services.rag_pipeline import query_documents, get_vector_store
    from app.services.embedder import get_embedder

    print(f"\n{'='*60}")
    print(f"  Evaluating: strategy={strategy}  model={model_key}")
    print(f"{'='*60}")

    embedder = get_embedder(model_key)
    store = get_vector_store(embedder.dimensionality)

    if store.count == 0:
        print("  Vector store is empty — ingesting PDFs first...")
        ingest_for_eval(strategy, model_key)

    all_precision: Dict[int, List[float]] = {k: [] for k in top_k_values}
    all_recall:    Dict[int, List[float]] = {k: [] for k in top_k_values}
    all_ndcg:      Dict[int, List[float]] = {k: [] for k in top_k_values}
    mrr_scores: List[float] = []

    for item in EVAL_SET:
        qid   = item["id"]
        query = item["query"]
        kws   = item["keywords"]

        result = query_documents(query, model_key, top_k=max(top_k_values),
                                 filter_strategy=strategy)
        results = result.get("results", [])
        retrieved_flags = [is_relevant(r.get("chunk_text", ""), kws) for r in results]

        # Count total relevant in store (rough — scan top-50)
        all_results = query_documents(query, model_key, top_k=50)
        total_rel = sum(
            is_relevant(r.get("chunk_text", ""), kws)
            for r in all_results.get("results", [])
        )
        total_rel = max(1, total_rel)  # avoid div-by-zero

        mrr = reciprocal_rank(retrieved_flags)
        mrr_scores.append(mrr)

        for k in top_k_values:
            all_precision[k].append(precision_at_k(retrieved_flags, k))
            all_recall[k].append(recall_at_k(retrieved_flags, total_rel, k))
            all_ndcg[k].append(ndcg_at_k(retrieved_flags, k))

        print(f"  [{qid}] P@5={precision_at_k(retrieved_flags, 5):.2f}  "
              f"R@5={recall_at_k(retrieved_flags, total_rel, 5):.2f}  "
              f"MRR={mrr:.2f}  NDCG@5={ndcg_at_k(retrieved_flags, 5):.2f}")

    def avg(lst): return round(sum(lst) / len(lst), 4) if lst else 0.0

    summary = {
        "strategy": strategy,
        "model": model_key,
        "MRR": avg(mrr_scores),
    }
    for k in top_k_values:
        summary[f"P@{k}"]    = avg(all_precision[k])
        summary[f"R@{k}"]    = avg(all_recall[k])
        summary[f"NDCG@{k}"] = avg(all_ndcg[k])

    print(f"\n  SUMMARY → MRR={summary['MRR']}  "
          f"P@5={summary['P@5']}  R@5={summary['R@5']}  NDCG@5={summary['NDCG@5']}")
    return summary


def main():
    STRATEGIES = ["fixed", "recursive", "layout_aware"]
    MODELS     = ["minilm", "bge"]
    results    = []

    for strategy in STRATEGIES:
        for model_key in MODELS:
            try:
                ingest_for_eval(strategy, model_key)
                row = evaluate(strategy, model_key)
                results.append(row)
            except Exception as e:
                print(f"  [ERROR] {strategy}/{model_key}: {e}")

    # Save
    out = Path("retrieval_eval_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nRetrieval eval results saved to: {out.resolve()}")

    # Print comparison matrix
    print("\n\n=== RETRIEVAL QUALITY MATRIX (NDCG@5) ===")
    print(f"{'Strategy':<18}", end="")
    for m in MODELS:
        print(f"{m:>12}", end="")
    print()
    for strategy in STRATEGIES:
        print(f"{strategy:<18}", end="")
        for model_key in MODELS:
            match = next((r for r in results
                          if r["strategy"] == strategy and r["model"] == model_key), None)
            val = f"{match['NDCG@5']:.4f}" if match else "N/A"
            print(f"{val:>12}", end="")
        print()

    # Recommend best
    if results:
        best = max(results, key=lambda r: r.get("NDCG@5", 0))
        print(f"\n★ RECOMMENDED DEFAULT: strategy='{best['strategy']}' "
              f"model='{best['model']}' (NDCG@5={best.get('NDCG@5', 0):.4f})")


if __name__ == "__main__":
    main()
