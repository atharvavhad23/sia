import json
from fastapi.encoders import jsonable_encoder
from app.services.pdfparser import PDFParserService

data = PDFParserService.extract_hybrid_text("04_Atharva_9.pdf")
try:
    jsonable_encoder(data)
    print("FastAPI Serialization OK")
except Exception as e:
    print("FastAPI Serialization Error:", e)
