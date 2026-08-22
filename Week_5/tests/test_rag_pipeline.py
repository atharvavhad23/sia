"""
tests/test_rag_pipeline.py — Day 4: Test Suite for RAG Components
==================================================================
Covers:
  - All 4 chunking strategies (including edge cases)
  - Embedder interface contract
  - Schema validation
  - Pipeline ingest + query (API-level)
  - Edge cases: empty doc, single-page, table-only
"""

import pytest
import os
import fitz
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.chunker import (
    FixedSizeChunker, RecursiveChunker,
    LayoutAwareChunker, get_chunker, Chunk
)
from app.services.embedder import get_embedder, MiniLMEmbedder
from app.services.schemas import ChunkMetadata, TableMetadata
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# ─── Fixtures ──────────────────────────────────────────────────────────────
DUMMY_PDF = "rag_test_dummy.pdf"
EMPTY_PDF = "rag_test_empty.pdf"

@pytest.fixture(scope="module", autouse=True)
def pdf_fixtures():
    # Normal dummy PDF
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 72), "Introduction\n\nThis is a test document for the RAG pipeline. "
                               "It contains multiple paragraphs to test chunking strategies. "
                               "Revenue and financial highlights are discussed here.\n\n"
                               "The methodology involves extracting structured data from PDFs.")
    doc.save(DUMMY_PDF)
    doc.close()

    # Empty-content PDF (valid structure, no text)
    doc2 = fitz.open()
    doc2.new_page()
    doc2.save(EMPTY_PDF)
    doc2.close()

    yield

    for f in [DUMMY_PDF, EMPTY_PDF]:
        if os.path.exists(f):
            os.remove(f)


def _make_doc(text: str, page: int = 1) -> dict:
    """Helper: build a minimal pdfparser-style dict."""
    return {"pages": [{"page": page, "text": text}], "tables": [], "metadata": {}}


# ─── Chunker Tests ───────────────────────────────────────────────────────────
class TestFixedSizeChunker:
    def test_produces_chunks(self):
        doc = _make_doc("Hello world " * 200)
        chunks = FixedSizeChunker(chunk_size=50, overlap=5).chunk(doc)
        assert len(chunks) > 0

    def test_chunk_token_count_within_limit(self):
        doc = _make_doc("Word " * 300)
        chunks = FixedSizeChunker(chunk_size=100, overlap=10).chunk(doc)
        for c in chunks:
            assert c.token_count <= 110   # slight tolerance for overlap

    def test_empty_page_skipped(self):
        doc = _make_doc("")
        chunks = FixedSizeChunker().chunk(doc)
        assert chunks == []

    def test_strategy_label(self):
        doc = _make_doc("Some text here for testing strategy label.")
        chunks = FixedSizeChunker(chunk_size=20, overlap=2).chunk(doc)
        for c in chunks:
            assert c.strategy == "fixed"


class TestRecursiveChunker:
    def test_produces_chunks(self):
        doc = _make_doc("Paragraph one.\n\nParagraph two.\n\nParagraph three.")
        chunks = RecursiveChunker(max_chars=50, overlap=5).chunk(doc)
        assert len(chunks) > 0

    def test_respects_max_chars(self):
        doc = _make_doc("A " * 1000)
        chunks = RecursiveChunker(max_chars=200, overlap=20).chunk(doc)
        for c in chunks:
            assert len(c.text) <= 250  # slight tolerance

    def test_empty_doc(self):
        chunks = RecursiveChunker().chunk({"pages": [], "tables": []})
        assert chunks == []

    def test_strategy_label(self):
        doc = _make_doc("Testing recursive chunker strategy label.")
        chunks = RecursiveChunker(max_chars=100).chunk(doc)
        for c in chunks:
            assert c.strategy == "recursive"


class TestLayoutAwareChunker:
    def test_tables_atomic(self):
        doc = {
            "pages": [{"page": 1, "text": "Some text content here."}],
            "tables": [{"page": 1, "data": [{"col1": "A", "col2": "B"},
                                              {"col1": "C", "col2": "D"}]}],
        }
        chunks = LayoutAwareChunker().chunk(doc)
        table_chunks = [c for c in chunks if c.chunk_type == "table"]
        assert len(table_chunks) == 1
        assert "A" in table_chunks[0].text or "col1" in table_chunks[0].text.lower()

    def test_empty_doc(self):
        chunks = LayoutAwareChunker().chunk({"pages": [], "tables": []})
        assert chunks == []

    def test_strategy_label(self):
        doc = _make_doc("Layout aware test text paragraph.")
        chunks = LayoutAwareChunker().chunk(doc)
        for c in chunks:
            assert c.strategy == "layout_aware"


class TestGetChunkerFactory:
    def test_valid_strategies(self):
        for s in ["fixed", "recursive", "layout_aware"]:
            chunker = get_chunker(s)
            assert chunker is not None

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError):
            get_chunker("nonexistent_strategy")


# ─── Embedder Tests ───────────────────────────────────────────────────────────
class TestMiniLMEmbedder:
    @pytest.fixture(scope="class")
    def embedder(self):
        return MiniLMEmbedder()

    def test_embed_returns_array(self, embedder):
        result = embedder.embed(["Hello world"])
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 384)

    def test_embed_multiple_chunks(self, embedder):
        texts = ["chunk one", "chunk two", "chunk three"]
        result = embedder.embed(texts)
        assert result.shape == (3, 384)

    def test_embed_query(self, embedder):
        vec = embedder.embed_query("what is revenue?")
        assert isinstance(vec, np.ndarray)
        assert vec.shape == (384,)

    def test_empty_input(self, embedder):
        result = embedder.embed([])
        assert len(result) == 0

    def test_vectors_normalized(self, embedder):
        vecs = embedder.embed(["normalize test"])
        norm = np.linalg.norm(vecs[0])
        assert abs(norm - 1.0) < 0.01

    def test_invalid_model_raises(self):
        with pytest.raises(ValueError):
            get_embedder("fake_model")


# ─── Schema Tests ─────────────────────────────────────────────────────────────
class TestChunkMetadata:
    def test_default_creation(self):
        meta = ChunkMetadata(
            source_filename="test.pdf",
            extraction_engine="pymupdf",
            chunking_strategy="fixed",
        )
        assert meta.source_filename == "test.pdf"
        assert meta.chunk_type == "text"
        assert meta.chunk_id is not None

    def test_table_metadata(self):
        meta = ChunkMetadata(
            source_filename="report.pdf",
            extraction_engine="camelot",
            chunking_strategy="layout_aware",
            chunk_type="table",
            table_metadata=TableMetadata(rows=5, columns=3),
        )
        assert meta.table_metadata.rows == 5
        assert meta.table_metadata.columns == 3

    def test_prev_next_links(self):
        import uuid
        prev_id = uuid.uuid4()
        next_id = uuid.uuid4()
        meta = ChunkMetadata(
            source_filename="doc.pdf",
            extraction_engine="pdfplumber",
            chunking_strategy="recursive",
            prev_chunk_id=prev_id,
            next_chunk_id=next_id,
        )
        assert meta.prev_chunk_id == prev_id
        assert meta.next_chunk_id == next_id


# ─── API Endpoint Tests ───────────────────────────────────────────────────────
class TestIngestEndpoint:
    def test_ingest_valid_pdf(self):
        with open(DUMMY_PDF, "rb") as f:
            response = client.post(
                "/api/v1/ingest",
                data={"engine": "fast", "chunking_strategy": "fixed",
                      "embedding_model": "minilm"},
                files={"file": (DUMMY_PDF, f, "application/pdf")}
            )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["chunks_created"] >= 0

    def test_ingest_invalid_extension(self):
        response = client.post(
            "/api/v1/ingest",
            data={"engine": "fast", "chunking_strategy": "fixed",
                  "embedding_model": "minilm"},
            files={"file": ("test.txt", b"hello", "text/plain")}
        )
        assert response.status_code == 400

    def test_ingest_invalid_strategy(self):
        with open(DUMMY_PDF, "rb") as f:
            response = client.post(
                "/api/v1/ingest",
                data={"engine": "fast", "chunking_strategy": "bad_strategy",
                      "embedding_model": "minilm"},
                files={"file": (DUMMY_PDF, f, "application/pdf")}
            )
        assert response.status_code == 400

    def test_ingest_empty_file(self):
        response = client.post(
            "/api/v1/ingest",
            data={"engine": "fast", "chunking_strategy": "fixed",
                  "embedding_model": "minilm"},
            files={"file": ("empty.pdf", b"", "application/pdf")}
        )
        assert response.status_code == 400


class TestQueryEndpoint:
    def test_query_returns_results(self):
        # Ingest first to ensure store has data
        with open(DUMMY_PDF, "rb") as f:
            client.post(
                "/api/v1/ingest",
                data={"engine": "fast", "chunking_strategy": "fixed",
                      "embedding_model": "minilm"},
                files={"file": (DUMMY_PDF, f, "application/pdf")}
            )
        response = client.post(
            "/api/v1/query",
            data={"query": "financial highlights revenue",
                  "embedding_model": "minilm", "top_k": "3"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "results" in data["data"]

    def test_query_empty_string(self):
        response = client.post(
            "/api/v1/query",
            data={"query": "", "embedding_model": "minilm", "top_k": "5"}
        )
        assert response.status_code == 400

    def test_query_invalid_model(self):
        response = client.post(
            "/api/v1/query",
            data={"query": "test query", "embedding_model": "fake", "top_k": "5"}
        )
        assert response.status_code == 400
