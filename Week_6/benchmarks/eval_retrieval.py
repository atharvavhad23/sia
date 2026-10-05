import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Week_6.retrieval.search_algorithms import (
    DenseSearcher, SparseSearcher, HybridSearcher, RerankingSearcher
)

def evaluate_retrieval(results, ground_truth_ids, k):
    """Calculate Precision@K and Recall@K"""
    retrieved_ids = [res[0] for res in results[:k]]
    
    # Precision@K: How many retrieved chunks are relevant?
    relevant_retrieved = sum(1 for cid in retrieved_ids if cid in ground_truth_ids)
    precision = relevant_retrieved / k if k > 0 else 0
    
    # Recall@K: How many relevant chunks were retrieved?
    # For our synthetic dataset, there's usually 1 or a few ground truth chunks
    recall = relevant_retrieved / len(ground_truth_ids) if ground_truth_ids else 0
    
    return precision, recall

def calculate_mrr(results, ground_truth_ids):
    """Calculate Mean Reciprocal Rank"""
    retrieved_ids = [res[0] for res in results]
    for rank, cid in enumerate(retrieved_ids):
        if cid in ground_truth_ids:
            return 1.0 / (rank + 1)
    return 0.0

def run_benchmarks():
    dataset_dir = Path(__file__).parent.parent / "dataset"
    
    with open(dataset_dir / "ground_truth.json", "r", encoding="utf-8") as f:
        qa_pairs = json.load(f)
        
    with open(dataset_dir / "corpus_chunks.json", "r", encoding="utf-8") as f:
        corpus = json.load(f)
        
    print(f"Loaded {len(qa_pairs)} queries and {len(corpus)} chunks.")
    
    print("Initializing Searchers...")
    searchers = {
        "Sparse (BM25)": SparseSearcher(corpus),
        "Dense (MiniLM)": DenseSearcher(corpus),
        "Hybrid (RRF)": HybridSearcher(corpus),
        "Reranker (Cross-Encoder)": RerankingSearcher(corpus)
    }
    
    results_summary = {}
    
    for name, searcher in searchers.items():
        print(f"--- Evaluating {name} ---")
        latencies = []
        p3_list, r3_list = [], []
        p5_list, r5_list = [], []
        mrr_list = []
        
        for qa in qa_pairs:
            query = qa["query"]
            gt_ids = qa["ground_truth_chunk_ids"]
            
            t0 = time.perf_counter()
            # Top 10 to measure MRR properly
            results = searcher.search(query, top_k=10)
            latencies.append(time.perf_counter() - t0)
            
            p3, r3 = evaluate_retrieval(results, gt_ids, k=3)
            p5, r5 = evaluate_retrieval(results, gt_ids, k=5)
            mrr = calculate_mrr(results, gt_ids)
            
            p3_list.append(p3)
            r3_list.append(r3)
            p5_list.append(p5)
            r5_list.append(r5)
            mrr_list.append(mrr)
            
        avg_latency_ms = (sum(latencies) / len(latencies)) * 1000
        
        metrics = {
            "avg_latency_ms": round(avg_latency_ms, 2),
            "precision@3": round(sum(p3_list) / len(p3_list), 4),
            "recall@3": round(sum(r3_list) / len(r3_list), 4),
            "precision@5": round(sum(p5_list) / len(p5_list), 4),
            "recall@5": round(sum(r5_list) / len(r5_list), 4),
            "mrr": round(sum(mrr_list) / len(mrr_list), 4),
        }
        
        results_summary[name] = metrics
        print(f"Latency: {metrics['avg_latency_ms']}ms | Recall@3: {metrics['recall@3']} | MRR: {metrics['mrr']}")
        
    out_dir = Path(__file__).parent
    with open(out_dir / "retrieval_metrics.json", "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
        
    print("\nBenchmark completed. Results saved to retrieval_metrics.json")

if __name__ == "__main__":
    run_benchmarks()
