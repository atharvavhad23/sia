"""
llm.py \u2014 Generative RAG Answer Synthesis (Gemini)
==================================================
Wraps the Google Gemini API to synthesize a conversational answer
from retrieved LanceDB chunks. Supports both batch and streaming modes.

DESIGN DECISIONS:
  - 30-second timeout prevents blocking a worker indefinitely on API hangs.
  - Graceful fallback: if the API is down or the key is missing, the function
    returns a safe string instead of raising, so the /query endpoint never 500s.
  - Streaming: generate_rag_answer_stream() yields text tokens via a generator,
    intended for SSE delivery via the /api/v1/query/stream endpoint.
  - Model: gemini-3.5-flash (confirmed available; gemini-1.5-flash returns 404
    on this API key as of Week 8 consolidation audit).
"""
import os
import json
import logging
import requests
from typing import List, Dict, Any, Generator

logger = logging.getLogger("sia.llm")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
GEMINI_TIMEOUT = int(os.getenv("GEMINI_TIMEOUT_SECONDS", "30"))


def _build_context(retrieved_chunks: List[Dict[str, Any]]) -> str:
    """Assemble the context block from retrieved chunks for the prompt."""
    context = ""
    for i, chunk in enumerate(retrieved_chunks):
        text = chunk.get("chunk_text", "")
        title = chunk.get("section_title") or f"Document {i + 1}"
        page = chunk.get("page_number", "?")
        source = chunk.get("source_filename", "Unknown")
        context += f"--- Source {i + 1}: {source}, Page {page}, Section: {title} ---\n{text}\n\n"
    return context


def _build_prompt(query: str, context: str, chat_history: List[Dict] = None) -> str:
    """Build the Gemini prompt, optionally including chat history for multi-turn context."""
    history_block = ""
    if chat_history:
        for turn in chat_history[-6:]:  # Keep last 6 turns to stay within context window
            role = turn.get("role", "user")
            content = turn.get("content", "")
            history_block += f"{role.upper()}: {content}\n"
        history_block = f"\nCONVERSATION HISTORY (for context):\n{history_block}\n"

    return f"""You are an intelligent document analysis AI called SIA.
You must answer the user's question using ONLY the context provided below.
If the answer is not in the context, say: "I cannot find the answer to this question in the provided documents."
Be concise, clear, and professional. Use markdown formatting (bold, bullet points) when it improves readability.
Always mention the source page number when citing specific facts.
{history_block}
DOCUMENT CONTEXT:
{context}

USER QUESTION: {query}
"""


def generate_rag_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    chat_history: List[Dict] = None,
) -> str:
    """
    Synthesize a full answer from retrieved chunks. Returns a string.
    Falls back gracefully if the API key is missing or the call fails.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Generative AI disabled.")
        return None  # None signals UI to skip the AI box entirely

    try:
        context = _build_context(retrieved_chunks)
        prompt = _build_prompt(query, context, chat_history)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        response = requests.post(url, headers=headers, json=payload, timeout=GEMINI_TIMEOUT)
        response.raise_for_status()
        
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"Gemini API error: {e}", exc_info=True)
        return f"*AI synthesis unavailable* \u2014 showing raw document matches only. (Error: {type(e).__name__})"


def generate_rag_answer_stream(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    chat_history: List[Dict] = None,
) -> Generator[str, None, None]:
    """
    Stream Gemini's answer token-by-token. Yields text chunks as they arrive.
    Designed for Server-Sent Events (SSE) delivery.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        yield "AI synthesis unavailable \u2014 GEMINI_API_KEY not configured."
        return

    try:
        context = _build_context(retrieved_chunks)
        prompt = _build_prompt(query, context, chat_history)

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:streamGenerateContent?alt=sse"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
        payload = {"contents": [{"parts": [{"text": prompt}]}]}

        with requests.post(url, headers=headers, json=payload, stream=True, timeout=GEMINI_TIMEOUT) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            text = data["candidates"][0]["content"]["parts"][0]["text"]
                            if text:
                                yield text
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                            
    except Exception as e:
        logger.error(f"Gemini stream error: {e}", exc_info=True)
        if "timeout" in str(e).lower() or "connect" in type(e).__name__.lower():
            yield "\n\n*The AI model endpoint is currently overloaded or unreachable. Please wait a moment and try again.*"
        else:
            yield f"\n\n*Stream interrupted: {type(e).__name__} - {str(e)}*"
