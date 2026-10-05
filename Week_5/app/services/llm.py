import os
import logging
from typing import List, Dict, Any

logger = logging.getLogger("sia.llm")

def generate_rag_answer(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """
    Synthesize an answer from the retrieved context using Gemini 1.5 Flash.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not found in environment. Generative AI is disabled.")
        return "GEMINI_API_KEY is not configured in your .env file. Showing extractive results only."
        
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        # Build prompt
        context = ""
        for i, chunk in enumerate(retrieved_chunks):
            text = chunk.get("chunk_text", "")
            title = chunk.get("section_title", f"Document {i+1}")
            context += f"--- Source {i+1}: {title} ---\n{text}\n\n"
            
        prompt = f"""You are an intelligent financial and document analysis AI.
You must answer the user's question using ONLY the context provided below.
If the answer is not contained in the context, say "I cannot find the answer to this question in the provided documents."
Be concise, clear, and professional. You can use markdown formatting if needed.

CONTEXT:
{context}

USER QUESTION: {query}
"""
        response = client.models.generate_content(
            model='gemini-3.5-flash',
            contents=prompt,
        )
        return response.text
    except Exception as e:
        logger.error(f"Error calling Gemini API: {e}")
        return "An error occurred while generating the answer from the AI model."
