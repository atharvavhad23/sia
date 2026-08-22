"""
schemas.py — Day 2: Chunk Metadata Schema (Pydantic)
=====================================================
Defines the authoritative metadata model that is attached to every
chunk before it is stored in the vector store.

Design rationale (per-field justification):
  chunk_id          — unique handle for deduplication and logging
  document_id       — groups all chunks from the same source document
  source_filename   — traceability back to the original PDF filename
  extraction_engine — lets us A/B-test extraction quality differences
  chunking_strategy — key dimension in the retrieval quality matrix
  page_number       — lets the UI show "found on page X"
  section_title     — enables section-level filtering at retrieval time
  chunk_type        — distinguishes tables from prose; allows type-aware retrieval
  char_count        — quick size sanity-check without re-tokenizing
  token_count       — accurate size for context-window budgeting
  chunk_index       — ordered position; used to reconstruct reading order
  prev_chunk_id     — enables context-window expansion (fetch surrounding chunks)
  next_chunk_id     — same as above for the forward direction
  created_at        — audit trail and cache invalidation
  embedding_model   — must be stored so retrieval uses the same model for query
  table_metadata    — rows/columns count; useful for table-aware ranking
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class TableMetadata(BaseModel):
    rows: Optional[int] = None
    columns: Optional[int] = None


class ChunkMetadata(BaseModel):
    """
    Full metadata schema for a single RAG chunk.
    Stored alongside the embedding vector in the vector store.
    """
    chunk_id: UUID = Field(default_factory=uuid4)
    document_id: UUID = Field(default_factory=uuid4)
    source_filename: str
    extraction_engine: str  # "pymupdf" | "pdfplumber" | "camelot" | "hybrid"
    chunking_strategy: str  # "fixed" | "recursive" | "semantic" | "layout_aware"
    page_number: int = 0
    section_title: Optional[str] = None
    chunk_type: str = "text"   # "text" | "table" | "heading"
    char_count: int = 0
    token_count: int = 0
    chunk_index: int = 0
    prev_chunk_id: Optional[UUID] = None
    next_chunk_id: Optional[UUID] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    embedding_model: str = ""
    table_metadata: TableMetadata = Field(default_factory=TableMetadata)

    class Config:
        json_encoders = {UUID: str, datetime: lambda v: v.isoformat()}
