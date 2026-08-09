import pytest
from fastapi.testclient import TestClient
from app.main import app
import os
import fitz

client = TestClient(app)

# Create a dummy PDF for testing
DUMMY_PDF = "dummy_test.pdf"

@pytest.fixture(scope="module", autouse=True)
def setup_dummy_pdf():
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), "This is a test document.")
    doc.save(DUMMY_PDF)
    doc.close()
    yield
    if os.path.exists(DUMMY_PDF):
        os.remove(DUMMY_PDF)

def test_health_check():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "online", "service": "SIA Backend Utilities"}

def test_extract_invalid_file_extension():
    response = client.post(
        "/api/v1/extract",
        data={"engine": "fast", "output_format": "json"},
        files={"file": ("test.txt", b"Hello world", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only .pdf files are supported" in response.text

def test_extract_invalid_engine():
    with open(DUMMY_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fake_engine", "output_format": "json"},
            files={"file": (DUMMY_PDF, f, "application/pdf")}
        )
    assert response.status_code == 400
    assert "Engine must be" in response.text

def test_extract_fast_json():
    with open(DUMMY_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fast", "output_format": "json"},
            files={"file": (DUMMY_PDF, f, "application/pdf")}
        )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "data" in data
    assert data["data"]["engine"] == "PyMuPDF"

def test_extract_fast_markdown():
    with open(DUMMY_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fast", "output_format": "markdown"},
            files={"file": (DUMMY_PDF, f, "application/pdf")}
        )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "# Extracted PDF Data" in response.text
    assert "**Engine Used:** PyMuPDF" in response.text

def test_extract_corrupted_pdf():
    # Create a completely corrupted PDF that bypasses the magic number check
    CORRUPTED_PDF = "corrupt.pdf"
    with open(CORRUPTED_PDF, "wb") as f:
        f.write(b"%PDF-1.4\nNot a real PDF file")
        
    with open(CORRUPTED_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fast", "output_format": "json"},
            files={"file": (CORRUPTED_PDF, f, "application/pdf")}
        )
    assert response.status_code == 400
    assert "Corrupted or unreadable PDF" in response.text
    os.remove(CORRUPTED_PDF)

def test_empty_file_upload():
    response = client.post(
        "/api/v1/extract",
        data={"engine": "fast", "output_format": "json"},
        files={"file": ("empty.pdf", b"", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Empty File" in response.text

def test_invalid_pdf_signature():
    response = client.post(
        "/api/v1/extract",
        data={"engine": "fast", "output_format": "json"},
        files={"file": ("fake.pdf", b"MZ\x90\x00\x03\x00\x00\x00", "application/pdf")}
    )
    assert response.status_code == 400
    assert "Invalid File Signature" in response.text

def test_zero_page_pdf():
    ZERO_PAGE_PDF = "zero_page.pdf"
    with open(ZERO_PAGE_PDF, "wb") as f:
        # A minimal PDF structure with no pages
        f.write(b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Count 0\n/Kids []\n>>\nendobj\ntrailer\n<<\n/Size 3\n/Root 1 0 R\n>>\n%%EOF\n")
    
    with open(ZERO_PAGE_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fast", "output_format": "json"},
            files={"file": (ZERO_PAGE_PDF, f, "application/pdf")}
        )
    assert response.status_code == 400
    assert "PDF has 0 pages" in response.text
    os.remove(ZERO_PAGE_PDF)

def test_password_protected_pdf():
    PWD_PDF = "locked.pdf"
    doc = fitz.open()
    doc.new_page()
    doc.save(PWD_PDF, user_pw="secret", owner_pw="secret", encryption=fitz.PDF_ENCRYPT_AES_256)
    doc.close()
    
    with open(PWD_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "fast", "output_format": "json"},
            files={"file": (PWD_PDF, f, "application/pdf")}
        )
    assert response.status_code == 400
    assert "Password-protected" in response.text
    os.remove(PWD_PDF)

def test_extract_structural_json():
    with open(DUMMY_PDF, "rb") as f:
        response = client.post(
            "/api/v1/extract",
            data={"engine": "structural", "output_format": "json"},
            files={"file": (DUMMY_PDF, f, "application/pdf")}
        )
    assert response.status_code == 200
    assert response.json()["data"]["engine"] == "pdfplumber"
