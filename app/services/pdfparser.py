import fitz  # PyMuPDF
import pdfplumber
import logging
from typing import Dict, Any

logger = logging.getLogger("sia.pdfparser")
logging.basicConfig(level=logging.INFO)

class PDFParserService:
    @staticmethod
    def _validate_pdf(file_path: str):
        """Validate if PDF is corrupted or password-protected."""
        try:
            with fitz.open(file_path) as doc:
                if doc.needs_pass:
                    logger.warning(f"PDF requires password: {file_path}")
                    raise ValueError("Password-protected PDF")
        except fitz.FileDataError:
            logger.error(f"Corrupted PDF file: {file_path}")
            raise ValueError("Corrupted or unreadable PDF")
        except Exception as e:
            if isinstance(e, ValueError):
                raise
            logger.error(f"Failed to open PDF {file_path}: {e}")
            raise ValueError("Corrupted or unreadable PDF")
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
    def extract_hybrid_text(file_path: str) -> Dict[str, Any]:
        """
        Hybrid Approach: 
        Uses Camelot to extract highly accurate tables and PyMuPDF for blazing fast text extraction.
        """
        logger.info(f"Starting 'hybrid' extraction for {file_path}")
        PDFParserService._validate_pdf(file_path)
        
        metadata = {}
        text_content = []
        tables_data = []
        
        # 1. Extract tables with Camelot
        try:
            import camelot
            tables = camelot.read_pdf(file_path, pages='all', flavor='stream', suppress_stdout=True)
            for i, table in enumerate(tables):
                tables_data.append({
                    "table_index": i,
                    "page": table.page,
                    "data": table.df.fillna("").to_dict(orient="records")
                })
        except Exception:
            pass # No tables found or missing dependencies
            
        # 2. Extract fast text with PyMuPDF
        with fitz.open(file_path) as doc:
            metadata = doc.metadata
            for page_num, page in enumerate(doc):
                text_content.append({
                    "page": page_num + 1,
                    "text": page.get_text().strip()
                })
                
        return {
            "engine": "hybrid_camelot_pymupdf",
            "metadata": metadata,
            "pages": text_content,
            "tables": tables_data
        }