import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))

from app.services.rag_pipeline import ingest_document, query_documents, get_vector_store

print("=== 1. Checking Vector Store ===")
store = get_vector_store()
print("Current vector count in store:", store.count)

print("\n=== 2. Ingesting q3_report.pdf ===")
res = ingest_document("d:/sia-utilities/test_pdfs/financial/q3_report.pdf", "q3_report.pdf", "layout_aware", "minilm", "fast")
print("Ingest result:", res)

print("\n=== 3. Querying: 'What is the revenue?' ===")
q_res = query_documents("What is the total revenue?", "minilm", top_k=5)
print("Query result count:", len(q_res.get("results", [])))
for i, r in enumerate(q_res.get("results", [])):
    print(f"\n--- Result {i+1} (Score: {r.get('similarity_score')}) ---")
    print(f"File: {r.get('source_filename')} | Page: {r.get('page_number')} | Strategy: {r.get('chunking_strategy')}")
    print(f"Text:\n{r.get('chunk_text', '')[:300]}...")
