import pytest
import os
import fitz
from app.services.pdfparser import PDFParserService

DUMMY_PDF = "dummy_service_test.pdf"

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "Unit test document.")
    doc.save(DUMMY_PDF)
    doc.close()
    yield
    if os.path.exists(DUMMY_PDF):
        os.remove(DUMMY_PDF)

def test_extract_fast_text_success():
    result = PDFParserService.extract_fast_text(DUMMY_PDF)
    assert result["engine"] == "PyMuPDF"
    assert len(result["pages"]) == 1
    assert "Unit test document." in result["pages"][0]["text"]

def test_extract_structural_text_success():
    result = PDFParserService.extract_structural_text(DUMMY_PDF)
    assert result["engine"] == "pdfplumber"
    assert len(result["pages"]) == 1
    assert "Unit test document." in result["pages"][0]["text"]

def test_validate_pdf_corrupted():
    CORRUPTED = "bad.pdf"
    with open(CORRUPTED, "wb") as f:
        f.write(b"Not a pdf")
    
    with pytest.raises(ValueError, match="Corrupted or unreadable PDF"):
        PDFParserService._validate_pdf(CORRUPTED)
    
    os.remove(CORRUPTED)
