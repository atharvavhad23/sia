import json
import numpy as np
from typing import List, Dict, Any, Tuple
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer, CrossEncoder

class BaseSearcher:
    def __init__(self, corpus: List[Dict[str, Any]]):
        self.corpus = corpus
        self.chunk_ids = [c["chunk_id"] for c in corpus]
        self.texts = [c["text"] for c in corpus]

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Returns list of (chunk_id, score)"""
        raise NotImplementedError

class DenseSearcher(BaseSearcher):
    def __init__(self, corpus: List[Dict[str, Any]], model_name="all-MiniLM-L6-v2"):
        super().__init__(corpus)
        self.model = SentenceTransformer(model_name)
        # Precompute embeddings
        self.embeddings = self.model.encode(self.texts, normalize_embeddings=True)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        q_emb = self.model.encode([query], normalize_embeddings=True)[0]
        # Cosine similarity (since normalized, dot product = cosine)
        scores = np.dot(self.embeddings, q_emb)
        
        # Get top_k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices]

class SparseSearcher(BaseSearcher):
    def __init__(self, corpus: List[Dict[str, Any]]):
        super().__init__(corpus)
        # Simple tokenization by splitting on whitespace
        tokenized_corpus = [doc.lower().split() for doc in self.texts]
        self.bm25 = BM25Okapi(tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        tokenized_query = query.lower().split()
        scores = self.bm25.get_scores(tokenized_query)
        
        top_indices = np.argsort(scores)[::-1][:top_k]
        return [(self.chunk_ids[i], float(scores[i])) for i in top_indices]

class HybridSearcher(BaseSearcher):
    def __init__(self, corpus: List[Dict[str, Any]], rrf_k: int = 60):
        super().__init__(corpus)
        self.dense = DenseSearcher(corpus)
        self.sparse = SparseSearcher(corpus)
        self.rrf_k = rrf_k

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        # Get top 20 from both to ensure we have enough overlap
        dense_results = self.dense.search(query, top_k=20)
        sparse_results = self.sparse.search(query, top_k=20)
        
        # Calculate RRF score
        rrf_scores = {}
        
        for rank, (chunk_id, _) in enumerate(dense_results):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            
        for rank, (chunk_id, _) in enumerate(sparse_results):
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (self.rrf_k + rank + 1)
            
        # Sort by RRF score
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_results[:top_k]

class RerankingSearcher(BaseSearcher):
    def __init__(self, corpus: List[Dict[str, Any]]):
        super().__init__(corpus)
        self.hybrid = HybridSearcher(corpus)
        self.reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def search(self, query: str, top_k: int = 5) -> List[Tuple[str, float]]:
        # Step 1: Initial retrieval (get more candidates for reranking)
        base_results = self.hybrid.search(query, top_k=min(20, len(self.corpus)))
        
        if not base_results:
            return []
            
        # Extract the texts for the retrieved chunk IDs
        candidate_pairs = []
        candidate_chunk_ids = []
        
        chunk_id_to_text = {c["chunk_id"]: c["text"] for c in self.corpus}
        
        for chunk_id, _ in base_results:
            text = chunk_id_to_text.get(chunk_id, "")
            candidate_pairs.append([query, text])
            candidate_chunk_ids.append(chunk_id)
            
        # Step 2: Rerank using Cross-Encoder
        scores = self.reranker.predict(candidate_pairs)
        
        # Sort by cross-encoder score
        reranked = [(candidate_chunk_ids[i], float(scores[i])) for i in range(len(scores))]
        reranked.sort(key=lambda x: x[1], reverse=True)
        
        return reranked[:top_k]
