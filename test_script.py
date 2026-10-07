from app.services.pdfparser import PDFParserService
import json

try:
    result = PDFParserService.extract_ocr_text('/mnt/test_ocr.pdf')
    for p in result['pages']:
        print(f"Page {p['page']}: {len(p['text'])} characters extracted.")
except Exception as e:
    print(f"Error: {e}")
