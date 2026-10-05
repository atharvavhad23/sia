"""
chunker.py — Day 1: Chunking Strategy Module
=============================================
Implements 4 chunking strategies behind a common BaseChunker interface:
  1. FixedSizeChunker     — token-based with configurable overlap (tiktoken)
  2. RecursiveChunker     — hierarchical separator splitting
  3. SemanticChunker      — cosine-similarity breakpoint splitting
  4. LayoutAwareChunker   — uses pdfplumber heading/table boundaries

All chunkers accept the raw output dict from pdfparser.py and return
a List[Chunk] — no changes to pdfparser.py are required.
"""

import uuid
import logging
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger("sia.chunker")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '{"time":"%(asctime)s","level":"%(levelname)s","message":"%(message)s","name":"%(name)s"}'
    ))
    logger.addHandler(handler)
logger.propagate = False


# ─────────────────────────────────────────────
# Data model for a single chunk
# ─────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    page_number: int = 0
    chunk_type: str = "text"          # text | table | heading
    section_title: Optional[str] = None
    char_count: int = 0
    token_count: int = 0
    chunk_index: int = 0
    strategy: str = "unknown"
    source_metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self.char_count = len(self.text)


# ─────────────────────────────────────────────
# Base interface
# ─────────────────────────────────────────────
class BaseChunker(ABC):
    """All chunkers must implement chunk() accepting a pdfparser result dict."""

    @abstractmethod
    def chunk(self, document: Dict[str, Any]) -> List[Chunk]:
        """
        Args:
            document: output dict from PDFParserService.extract_*()
                      Expected keys: 'pages' (list of {page, text}),
                      optionally 'tables', 'metadata'.
        Returns:
            List[Chunk]
        """
        ...

    # ── shared helper: count tokens with tiktoken ──────────────────────────
    @staticmethod
    def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
        try:
            import tiktoken
            enc = tiktoken.get_encoding(encoding_name)
            return len(enc.encode(text))
        except Exception:
            # Fallback: rough approximation if tiktoken unavailable
            return max(1, len(text) // 4)


# ─────────────────────────────────────────────
# Strategy 1: Fixed-Size Chunker
# ─────────────────────────────────────────────
class FixedSizeChunker(BaseChunker):
    """
    Splits document text into token-based windows of fixed size with overlap.
    Uses tiktoken for accurate token counting (not character approximation).

    Args:
        chunk_size:  target token count per chunk (default 512)
        overlap:     token overlap between consecutive chunks (default 50)
    """
    def __init__(self, chunk_size: int = 512, overlap: int = 50):
        self.chunk_size = chunk_size
        self.overlap = overlap
        import tiktoken
        self.enc = tiktoken.get_encoding("cl100k_base")

    def chunk(self, document: Dict[str, Any]) -> List[Chunk]:
        logger.info(f"FixedSizeChunker: starting (size={self.chunk_size}, overlap={self.overlap})")
        chunks: List[Chunk] = []
        idx = 0

        for page_data in document.get("pages", []):
            page_num = page_data.get("page", 0)
            text = page_data.get("text", "").strip()
            if not text:
                continue

            tokens = self.enc.encode(text)
            start = 0
            while start < len(tokens):
                end = min(start + self.chunk_size, len(tokens))
                chunk_tokens = tokens[start:end]
                chunk_text = self.enc.decode(chunk_tokens)

                c = Chunk(
                    text=chunk_text,
                    page_number=page_num,
                    chunk_type="text",
                    chunk_index=idx,
                    strategy="fixed",
                    token_count=len(chunk_tokens),
                )
                chunks.append(c)
                idx += 1
                start += self.chunk_size - self.overlap

        logger.info(f"FixedSizeChunker: produced {len(chunks)} chunks")
        return chunks


# ─────────────────────────────────────────────
# Strategy 2: Recursive Chunker
# ─────────────────────────────────────────────
class RecursiveChunker(BaseChunker):
    """
    Hierarchical separator-based splitting:
      paragraph → newline → sentence → word
    Inspired by LangChain's RecursiveCharacterTextSplitter but
    implemented without mandatory LangChain dependency.

    Args:
        max_chars:  max characters per chunk (default 1500)
        overlap:    character overlap (default 150)
    """
    SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

    def __init__(self, max_chars: int = 1500, overlap: int = 150):
        self.max_chars = max_chars
        self.overlap = overlap

    def _split_text(self, text: str, sep_index: int = 0) -> List[str]:
        """
        Recursively split text using the separator hierarchy.
        sep_index tracks which separator level we are currently at,
        preventing re-trying the same separator and hitting recursion limits.
        """
        # Base case: exceeded all separators — hard split by character count
        if sep_index >= len(self.SEPARATORS):
            parts = [text[i:i + self.max_chars]
                     for i in range(0, len(text), max(1, self.max_chars - self.overlap))]
            return [p for p in parts if p.strip()]

        sep = self.SEPARATORS[sep_index]

        # Empty separator = last resort hard split
        if sep == "":
            parts = [text[i:i + self.max_chars]
                     for i in range(0, len(text), max(1, self.max_chars - self.overlap))]
            return [p for p in parts if p.strip()]

        raw_parts = text.split(sep)

        # If this separator doesn't split the text, try the next one
        if len(raw_parts) <= 1:
            return self._split_text(text, sep_index + 1)

        merged: List[str] = []
        current = ""
        for part in raw_parts:
            candidate = (current + sep + part).strip() if current else part.strip()
            if len(candidate) <= self.max_chars:
                current = candidate
            else:
                if current:
                    merged.append(current)
                # Part still too long — descend to the NEXT separator level
                if len(part) > self.max_chars:
                    merged.extend(self._split_text(part, sep_index + 1))
                    current = ""
                else:
                    current = part.strip()
        if current:
            merged.append(current)
        return merged if merged else [text]

    def chunk(self, document: Dict[str, Any]) -> List[Chunk]:
        logger.info(f"RecursiveChunker: starting (max_chars={self.max_chars}, overlap={self.overlap})")
        chunks: List[Chunk] = []
        idx = 0

        for page_data in document.get("pages", []):
            page_num = page_data.get("page", 0)
            text = page_data.get("text", "").strip()
            if not text:
                continue

            pieces = self._split_text(text)
            for piece in pieces:
                if not piece.strip():
                    continue
                c = Chunk(
                    text=piece,
                    page_number=page_num,
                    chunk_type="text",
                    chunk_index=idx,
                    strategy="recursive",
                    token_count=self._count_tokens(piece),
                )
                chunks.append(c)
                idx += 1

        logger.info(f"RecursiveChunker: produced {len(chunks)} chunks")
        return chunks


# ─────────────────────────────────────────────
# Strategy 3: Semantic Chunker
# ─────────────────────────────────────────────
class SemanticChunker(BaseChunker):
    """
    Embeds consecutive sentence groups and splits at cosine-similarity
    breakpoints (drop below the Nth percentile = new chunk boundary).

    Requires: sentence-transformers
    Args:
        model_name:  sentence-transformer model (default all-MiniLM-L6-v2)
        percentile:  similarity breakpoint threshold (default 25 = bottom 25%)
        window:      number of sentences per group for embedding (default 3)
    """
    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        percentile: float = 25.0,
        window: int = 3,
    ):
        self.model_name = model_name
        self.percentile = percentile
        self.window = window
        self._model = None  # lazy load

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"SemanticChunker: loading model {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model

    @staticmethod
    def _cosine(a, b) -> float:
        import numpy as np
        na, nb = np.linalg.norm(a), np.linalg.norm(b)
        if na == 0 or nb == 0:
            return 0.0
        return float(np.dot(a, b) / (na * nb))

    def _sentences(self, text: str) -> List[str]:
        """Split text into sentences by period/newline."""
        import re
        raw = re.split(r'(?<=[.!?])\s+|\n+', text)
        return [s.strip() for s in raw if s.strip()]

    def chunk(self, document: Dict[str, Any]) -> List[Chunk]:
        import numpy as np
        logger.info(f"SemanticChunker: starting (model={self.model_name}, percentile={self.percentile})")
        model = self._get_model()
        chunks: List[Chunk] = []
        idx = 0

        for page_data in document.get("pages", []):
            page_num = page_data.get("page", 0)
            text = page_data.get("text", "").strip()
            if not text:
                continue

            sentences = self._sentences(text)
            if len(sentences) <= self.window:
                # Page too small — treat it as single chunk
                c = Chunk(
                    text=text,
                    page_number=page_num,
                    chunk_type="text",
                    chunk_index=idx,
                    strategy="semantic",
                    token_count=self._count_tokens(text),
                )
                chunks.append(c)
                idx += 1
                continue

            # Build sentence-group embeddings
            groups = [" ".join(sentences[i:i + self.window])
                      for i in range(len(sentences))]
            embeddings = model.encode(groups, batch_size=32, show_progress_bar=False)

            # Compute consecutive similarities
            sims = [self._cosine(embeddings[i], embeddings[i + 1])
                    for i in range(len(embeddings) - 1)]

            # Breakpoint threshold = Nth percentile of similarities
            threshold = float(np.percentile(sims, self.percentile))

            # Build chunks
            current_sents: List[str] = [sentences[0]]
            for i, sim in enumerate(sims):
                if sim < threshold:
                    chunk_text = " ".join(current_sents)
                    c = Chunk(
                        text=chunk_text,
                        page_number=page_num,
                        chunk_type="text",
                        chunk_index=idx,
                        strategy="semantic",
                        token_count=self._count_tokens(chunk_text),
                    )
                    chunks.append(c)
                    idx += 1
                    current_sents = []
                if i + 1 < len(sentences):
                    current_sents.append(sentences[i + 1])

            if current_sents:
                chunk_text = " ".join(current_sents)
                c = Chunk(
                    text=chunk_text,
                    page_number=page_num,
                    chunk_type="text",
                    chunk_index=idx,
                    strategy="semantic",
                    token_count=self._count_tokens(chunk_text),
                )
                chunks.append(c)
                idx += 1

        logger.info(f"SemanticChunker: produced {len(chunks)} chunks")
        return chunks


# ─────────────────────────────────────────────
# Strategy 4: Layout-Aware Chunker
# ─────────────────────────────────────────────
class LayoutAwareChunker(BaseChunker):
    """
    Chunks along natural document boundaries using the structural output
    from pdfparser.py (the 'hybrid' engine provides tables separately).

    Rules:
      - Never split a table mid-row; entire tables are single chunks.
      - Section headings (detected by ALL-CAPS or ending with ':') stay
        attached to the first paragraph that follows them.
      - Text paragraphs split on \n\n boundaries.

    Args:
        max_chars: soft cap per text chunk (default 2000)
    """
    def __init__(self, max_chars: int = 500):
        self.max_chars = max_chars

    def chunk(self, document: Dict[str, Any]) -> List[Chunk]:
        logger.info(f"LayoutAwareChunker: starting (max_chars={self.max_chars})")
        chunks: List[Chunk] = []
        idx = 0

        # 1. Tables: each table is an atomic chunk — never split
        for tbl in document.get("tables", []):
            page_num = tbl.get("page", 0)
            rows = tbl.get("data", [])
            table_text = "\n".join(
                " | ".join(str(v) for v in row.values())
                for row in rows
            ) if rows else ""
            if not table_text.strip():
                continue
            c = Chunk(
                text=table_text,
                page_number=page_num,
                chunk_type="table",
                chunk_index=idx,
                strategy="layout_aware",
                token_count=self._count_tokens(table_text),
                source_metadata={"rows": len(rows),
                                 "columns": len(rows[0]) if rows else 0},
            )
            chunks.append(c)
            idx += 1

        # 2. Text pages: granular section, project & bullet splitting
        import re
        header_re = re.compile(r'^(?:[A-Z\s]{3,35}:?|[A-Za-z0-9\s\-]+:|\d{1,2}\s+[A-Za-z]{3},\s+\d{4})')

        for page_data in document.get("pages", []):
            page_num = page_data.get("page", 0)
            text = page_data.get("text", "").strip()
            if not text:
                continue

            lines = [line.strip() for line in text.splitlines() if line.strip()]
            buffer = []
            curr_len = 0
            current_heading: Optional[str] = None

            for line in lines:
                is_bullet = line.startswith('•') or line.startswith('- ') or line.startswith('* ')
                is_header = bool(header_re.match(line)) and len(line) < 110

                if is_header and len(line) < 40 and (line.isupper() or line.endswith(':')):
                    current_heading = line

                # Flush buffer on logical topic boundary (header/date/bullet) if buffer already has content
                if (is_header or is_bullet) and curr_len > 180:
                    chunk_str = "\n".join(buffer).strip()
                    if chunk_str:
                        c = Chunk(
                            text=chunk_str,
                            page_number=page_num,
                            chunk_type="text",
                            section_title=current_heading,
                            chunk_index=idx,
                            strategy="layout_aware",
                            token_count=self._count_tokens(chunk_str),
                        )
                        chunks.append(c)
                        idx += 1
                    buffer = [line]
                    curr_len = len(line)
                else:
                    if curr_len + len(line) > self.max_chars and buffer:
                        chunk_str = "\n".join(buffer).strip()
                        if chunk_str:
                            c = Chunk(
                                text=chunk_str,
                                page_number=page_num,
                                chunk_type="text",
                                section_title=current_heading,
                                chunk_index=idx,
                                strategy="layout_aware",
                                token_count=self._count_tokens(chunk_str),
                            )
                            chunks.append(c)
                            idx += 1
                        buffer = [line]
                        curr_len = len(line)
                    else:
                        buffer.append(line)
                        curr_len += len(line)

            if buffer:
                chunk_str = "\n".join(buffer).strip()
                if chunk_str:
                    c = Chunk(
                        text=chunk_str,
                        page_number=page_num,
                        chunk_type="text",
                        section_title=current_heading,
                        chunk_index=idx,
                        strategy="layout_aware",
                        token_count=self._count_tokens(chunk_str),
                    )
                    chunks.append(c)
                    idx += 1

        logger.info(f"LayoutAwareChunker: produced {len(chunks)} chunks")
        return chunks


# ─────────────────────────────────────────────
# Factory helper
# ─────────────────────────────────────────────
def get_chunker(strategy: str, **kwargs) -> BaseChunker:
    """
    Factory: returns the correct chunker given a strategy string.
    Valid values: 'fixed', 'recursive', 'semantic', 'layout_aware'
    """
    MAP = {
        "fixed": FixedSizeChunker,
        "recursive": RecursiveChunker,
        "semantic": SemanticChunker,
        "layout_aware": LayoutAwareChunker,
    }
    if strategy not in MAP:
        raise ValueError(f"Unknown chunking strategy '{strategy}'. Choose from: {list(MAP)}")
    return MAP[strategy](**kwargs)
