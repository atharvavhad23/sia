import sys
import json
import uuid
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Week_5.app.services.chunker import get_chunker
from Week_5.app.services.pdfparser import PDFParserService

def generate_qa_dataset():
    pdf_path = Path(__file__).parent.parent.parent / "Week_5" / "temp_docs" / "b70892a7-3d21-476f-9319-a61233432f5c.pdf"
    
    # 1. Extract text and layout
    doc_elements = PDFParserService.extract_fast_text(str(pdf_path))

    
    # 2. Chunk it
    chunker = get_chunker("layout_aware", max_chars=500)
    chunks = chunker.chunk(doc_elements)
    
    # 3. Define QA pairs mapped to substrings that exist in the chunks
    # We will search the chunks for these exact substrings to find the "Ground Truth" chunk ID
    qa_definitions = [
        {
            "query": "What is NexaShield?",
            "ground_truth_substring": "NexaShield: Forensic-Grade Deepfake Detection System"
        },
        {
            "query": "What skills were used for NexaShield?",
            "ground_truth_substring": "PyTorch , OpenCV"
        },
        {
            "query": "What is the wildlife intelligence platform for Koyna?",
            "ground_truth_substring": "wildlife intelligence platform for Koyna Wildlife Sanctuary"
        },
        {
            "query": "What does the Water Quality Analysis System do?",
            "ground_truth_substring": "monitor, analyze, and visualize the water quality"
        },
        {
            "query": "Who is Atharva?",
            "ground_truth_substring": "Atharva Avhad"
        },
        {
            "query": "What tech stack is used in the personal portfolio?",
            "ground_truth_substring": "React, Three.js"
        },
        {
            "query": "What is the SIH project about?",
            "ground_truth_substring": "legal document summarization"
        },
        {
            "query": "What is the email id?",
            "ground_truth_substring": "atharvavhad23@gmail.com"
        }
    ]
    
    dataset = []
    
    for qa in qa_definitions:
        query = qa["query"]
        substring = qa["ground_truth_substring"]
        
        # Find all chunks containing this substring
        matching_chunk_ids = []
        for c in chunks:
            if substring.lower() in c.text.lower():
                matching_chunk_ids.append(c.chunk_id)
                
        if matching_chunk_ids:
            dataset.append({
                "query": query,
                "ground_truth_chunk_ids": matching_chunk_ids,
                "ground_truth_substring": substring
            })
        else:
            print(f"Warning: Substring not found for query '{query}': '{substring}'")
            
    # Also save the chunks to a JSON file so our search algorithms can index them
    chunks_data = [
        {
            "chunk_id": str(c.chunk_id),
            "text": c.text,
            "metadata": c.__dict__
        }
        for c in chunks
    ]
    
    out_dir = Path(__file__).parent
    
    with open(out_dir / "ground_truth.json", "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)
        
    with open(out_dir / "corpus_chunks.json", "w", encoding="utf-8") as f:
        json.dump(chunks_data, f, indent=2)
        
    print(f"Generated {len(dataset)} QA pairs and saved {len(chunks)} chunks.")

if __name__ == "__main__":
    generate_qa_dataset()
