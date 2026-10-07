import asyncio
import sys
import os

# Add the Week_5/app directory to sys.path so we can import services
sys.path.append(os.path.join(os.path.dirname(__file__), "Week_5"))

from app.services.rag_pipeline import SIA_RAG_Pipeline

async def main():
    rag = SIA_RAG_Pipeline()
    results = await rag.query_documents("tell me his project in summarized format")
    for i, c in enumerate(results["chunks"]):
        print(f"Chunk {i+1}: {len(c.get('chunk_text', ''))} bytes")
    
    # Try the one that failed
    print("\nTrying second query...")
    results2 = await rag.query_documents("what is sql injection")
    for i, c in enumerate(results2["chunks"]):
        print(f"Chunk {i+1}: {len(c.get('chunk_text', ''))} bytes")

asyncio.run(main())
