import fitz  # PyMuPDF
import pdfplumber
import logging
from typing import Dict, Any

logger = logging.getLogger("sia.pdfparser")
logging.basicConfig(level=logging.INFO)

class PDFCorruptedException(ValueError):
    """Raised when PDF structure is broken or invalid."""
    pass

class PDFPasswordProtectedException(ValueError):
    """Raised when PDF requires a password."""
    pass


class PDFParserService:
    @staticmethod
    def _validate_pdf(file_path: str):
        """Validate if PDF is corrupted or password-protected."""
        try:
            with fitz.open(file_path) as doc:
                if doc.needs_pass:
                    logger.warning(f"PDF requires password: {file_path}")
                    raise PDFPasswordProtectedException("Password-protected PDF")
                if doc.page_count == 0:
                    logger.warning(f"PDF has 0 pages: {file_path}")
                    raise PDFCorruptedException("PDF has 0 pages")
        except fitz.FileDataError:
            logger.error(f"Corrupted PDF file: {file_path}")
            raise PDFCorruptedException("Corrupted or unreadable PDF")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Failed to open PDF {file_path}: {e}")
            raise PDFCorruptedException("Corrupted or unreadable PDF")
    @staticmethod
    def extract_fast_text(file_path: str) -> Dict[str, Any]:
        """
        Extracts raw textual data rapidly using PyMuPDF.
        Ideal for high-throughput initial indexing in a RAG pipeline.
        """
        logger.info(f"Starting 'fast' extraction for {file_path}")
        PDFParserService._validate_pdf(file_path)
        
        text_content = []
        metadata = {}
        
        with fitz.open(file_path) as doc:
            metadata = doc.metadata
            for page_num, page in enumerate(doc):
                text_content.append({
                    "page": page_num + 1,
                    "text": page.get_text().strip()
                })
                
        return {
            "engine": "PyMuPDF",
            "metadata": metadata,
            "pages": text_content
        }

    @staticmethod
    def extract_structural_text(file_path: str) -> Dict[str, Any]:
        """
        Extracts text preserving basic layout coordinates using pdfplumber.
        Useful when boundary filtering or structural verification is required.
        """
        logger.info(f"Starting 'structural' extraction for {file_path}")
        PDFParserService._validate_pdf(file_path)
        
        text_content = []
        
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                extracted = page.extract_text()
                text_content.append({
                    "page": page_num + 1,
                    "text": extracted.strip() if extracted else ""
                })
                
        return {
            "engine": "pdfplumber",
            "pages": text_content
        }

    @staticmethod
    def _extract_tables_camelot(file_path: str):
        tables_data = []
        try:
            import camelot
            tables = camelot.read_pdf(file_path, pages='all', flavor='stream', suppress_stdout=True)
            for i, table in enumerate(tables):
                tables_data.append({
                    "table_index": i,
                    "page": table.page,
                    "data": table.df.fillna("").to_dict(orient="records")
                })
        except Exception as e:
            logger.warning(f"Camelot table extraction failed or no tables found: {e}")
        return tables_data

    @staticmethod
    def _extract_text_pymupdf(file_path: str):
        metadata = {}
        text_content = []
        with fitz.open(file_path) as doc:
            metadata = doc.metadata
            for page_num, page in enumerate(doc):
                text_content.append({
                    "page": page_num + 1,
                    "text": page.get_text().strip()
                })
        return metadata, text_content

    @staticmethod
    def extract_hybrid_text(file_path: str) -> Dict[str, Any]:
        """
        Hybrid Approach: 
        Uses Camelot to extract highly accurate tables and PyMuPDF for blazing fast text extraction.
        Runs in parallel (ThreadPoolExecutor) to massively optimize latency.
        """
        logger.info(f"Starting parallel 'hybrid' extraction for {file_path}")
        PDFParserService._validate_pdf(file_path)
        
        import concurrent.futures
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future_tables = executor.submit(PDFParserService._extract_tables_camelot, file_path)
            future_text = executor.submit(PDFParserService._extract_text_pymupdf, file_path)
            
            tables_data = future_tables.result()
            metadata, text_content = future_text.result()
                
        return {
            "engine": "hybrid_camelot_pymupdf",
            "metadata": metadata,
            "pages": text_content,
            "tables": tables_data
        }

    @staticmethod
    def extract_ocr_text(file_path: str) -> Dict[str, Any]:
        """
        OCR Approach:
        Uses pdf2image and pytesseract to convert PDF pages into images and run Optical Character Recognition.
        Essential for scanned documents or image-based PDFs without a text layer.
        """
        logger.info(f"Starting 'ocr' extraction for {file_path}")
        PDFParserService._validate_pdf(file_path)
        
        text_content = []
        try:
            from pdf2image import convert_from_path
            import pytesseract
            
            # Convert PDF pages to images
            images = convert_from_path(file_path)
            for page_num, image in enumerate(images):
                # Extract text using Tesseract
                text = pytesseract.image_to_string(image)
                text_content.append({
                    "page": page_num + 1,
                    "text": text.strip() if text else ""
                })
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            raise RuntimeError(f"OCR extraction failed: {e}")
            
        return {
            "engine": "ocr_pytesseract",
            "pages": text_content
        }