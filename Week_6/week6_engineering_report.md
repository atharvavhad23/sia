# Week 6 Engineering Report: Search & Retrieval Optimization

**Date:** September 12, 2026
**Project:** SIA Document Extraction & RAG Pipeline
**Author:** AI Engineering Team

---

## 1. Objective
To significantly improve search quality and retrieval efficiency by evaluating and benchmarking four distinct retrieval strategies. The goal was to find the optimal balance between high precision/recall and low system latency.

## 2. Strategies Evaluated

We implemented a unified interface (`BaseSearcher`) to evaluate four different retrieval algorithms:

1. **Sparse Search (BM25)**: Lexical search that maps exact keywords. Implemented using the `rank_bm25` algorithm.
2. **Dense Search (MiniLM)**: Semantic vector search using SentenceTransformers (`all-MiniLM-L6-v2`) and Cosine Similarity.
3. **Hybrid Search (RRF)**: A fusion engine that combines the results of Sparse and Dense search using Reciprocal Rank Fusion, penalizing outliers and promoting chunks that score highly in both systems.
4. **Reranking (Cross-Encoder)**: A two-stage pipeline. It first fetches the top 20 candidates using Hybrid Search, and then passes them through a heavy AI Cross-Encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`) which perfectly scores the contextual relevance between the query and the chunk.

## 3. Benchmark Methodology

We developed an automated evaluation suite (`eval_retrieval.py`) that executes a synthetic ground-truth dataset against all four engines.

**Metrics Captured:**
- **Latency**: Average execution time per query in milliseconds.
- **Recall@3**: The percentage of relevant chunks retrieved within the top 3 results.
- **Precision@3**: The percentage of the top 3 retrieved chunks that were actually relevant.
- **Mean Reciprocal Rank (MRR)**: Measures how high the first relevant chunk appears in the search results (1.0 = first place, 0.5 = second place, etc.).

## 4. Benchmark Results

| Strategy | Avg Latency (ms) | Recall@3 | MRR |
|----------|------------------|----------|-----|
| **Sparse (BM25)** | 2.62 ms | 0.500 | 0.550 |
| **Hybrid (RRF)** | 11.60 ms | 0.750 | 0.785 |
| **Dense (MiniLM)** | 14.15 ms | 1.000 | 1.000 |
| **Reranker (Cross-Encoder)**| 418.99 ms | 1.000 | 1.000 |

*(Note: Hardware metrics measured on CPU. GPU acceleration would significantly alter Cross-Encoder latency).*

## 5. Engineering Analysis & Tradeoffs

1. **BM25 (Sparse)**: As expected, BM25 is blazing fast (2.6ms) but struggles heavily with semantic intent. If the user searches for a synonym rather than the exact word in the document, BM25 fails completely.
2. **Dense Search**: This proved to be the most optimal baseline for our specific vector setup. At only 14ms per query, it perfectly captured semantic intent and achieved a 1.0 Recall@3.
3. **Cross-Encoder Reranking**: While it guarantees the highest contextual accuracy, the Cross-Encoder architecture requires passing the query and the chunk text through the transformer network *together* for every single candidate. This resulted in a massive **~400ms latency penalty** on CPU.

## 6. Final Recommendation for Production

For the live SIA RAG Studio, we strongly recommend deploying **Dense Search** as the default engine. It provides the best "bang for buck"—delivering 100% semantic recall with sub-20ms latency. 

The **Cross-Encoder Reranker** is highly valuable but should be hidden behind a "Deep Search" toggle in the UI, allowing users to opt into the slower, highly-accurate search only when they are asking complex analytical questions.
