import asyncio
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), "Week_5"))
from app.services.rag_pipeline import query_documents_for_stream

def main():
    results, _ = query_documents_for_stream("tell me his project in summarized format")
    total_len = 0
    for i, c in enumerate(results):
        text_len = len(c.get("chunk_text", ""))
        print(f"Chunk {i+1}: {text_len} bytes")
        total_len += text_len
    print(f"Total payload length: {total_len} bytes")

main()
