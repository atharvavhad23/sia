from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from app.services.pdfparser import PDFParserService
import shutil
import os
import logging
import traceback
import logging

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sia.api")

tags_metadata = [
    {
        "name": "System",
        "description": "Core system operations and health checks.",
    },
    {
        "name": "Extraction Engine",
        "description": "Core endpoints for processing PDFs, handling tables, and generating AI-ready outputs.",
    },
]

app = FastAPI(
    title="SIA Extraction Microservice",
    version="2.0.0",
    contact={"name": "Atharva Avhad (SIA Backend Engineering)"},
    openapi_tags=tags_metadata,
    docs_url=None,      # Disable default Swagger UI
    redoc_url=None,     # Disable default Redoc UI
)

TEMP_DIR = "temp_docs"
os.makedirs(TEMP_DIR, exist_ok=True)

# ---------------------------------------------------------
# Enterprise Error Handlers
# ---------------------------------------------------------
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Overrides default 422 error for a cleaner, unified JSON response."""
    errors = [{"field": ".".join(map(str, err["loc"])), "message": err["msg"]} for err in exc.errors()]
    logger.warning(f"Validation Error on {request.url.path}: {errors}")
    return JSONResponse(
        status_code=400,
        content={"success": False, "error": "Validation Error", "details": errors},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catches all unhandled exceptions to prevent crashing and leaking stack traces."""
    logger.error(f"Unhandled Exception on {request.url.path}: {exc}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": "Internal Server Error", "details": "An unexpected backend failure occurred."},
    )

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/docs", include_in_schema=False)
async def custom_docs():
    """Serve our beautiful custom documentation page."""
    with open("app/static/docs.html", "r", encoding="utf-8") as f:
        html = f.read()
    return HTMLResponse(content=html)

def json_to_markdown(data: dict) -> str:
    """Helper function to convert JSON output to a beautiful Markdown document."""
    md = f"# Extracted PDF Data\n\n"
    md += f"**Engine Used:** {data.get('engine', 'Unknown')}\n\n"
    
    if 'metadata' in data and data['metadata']:
        md += "## Metadata\n"
        for k, v in data['metadata'].items():
            if v:
                md += f"- **{k}**: {v}\n"
        md += "\n"
    
    if 'tables' in data and data['tables']:
        md += "## Extracted Tables\n\n"
        for table in data['tables']:
            md += f"### Table {table['table_index']} (Page {table['page']})\n"
            rows = table.get('data', [])
            if rows:
                headers = list(rows[0].keys())
                str_headers = [str(h).replace('\n', ' ') for h in headers]
                md += "| " + " | ".join(str_headers) + " |\n"
                md += "| " + " | ".join(["---"] * len(headers)) + " |\n"
                for row in rows:
                    md += "| " + " | ".join([str(row.get(h, "")).replace("\n", " ") for h in headers]) + " |\n"
            md += "\n"
            
    if 'pages' in data and data['pages']:
        md += "## Text Content\n\n"
        for page in data['pages']:
            md += f"### Page {page['page']}\n{page['text']}\n\n"
            
    return md

@app.get("/", tags=["System"], summary="System Health Check")
def health_check():
    """Returns the operational status of the SIA microservice."""
    return {
        "status": "online",
        "service": "SIA Backend Utilities"
    }

@app.post("/api/v1/extract", tags=["Extraction Engine"], summary="Extract Content from PDF Document")
async def extract_pdf(
    engine: str = Form("hybrid", description="Processing pipeline: 'fast', 'structural', or 'hybrid'"),
    output_format: str = Form("json", description="Response format: 'json' or 'markdown'"),
    file: UploadFile = File(..., description="The PDF document to be ingested and analyzed.")
):
    """
    **Upload a PDF document** to instantly extract raw text, metadata, and tables.
    
    Use the **hybrid** engine for documents containing financial grids or structured tables.
    """
    logger.info(f"Received extraction request: file={file.filename}, engine={engine}, format={output_format}")
    
    # 1. Validation Checks
    if not file.filename.endswith('.pdf'):
        logger.warning(f"Invalid file type uploaded: {file.filename}")
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid File Type", "details": "Only .pdf files are supported."})
    
    if engine not in ["fast", "structural", "hybrid"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid Engine", "details": "Engine must be 'fast', 'structural', or 'hybrid'."})
        
    if output_format not in ["json", "markdown"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid Format", "details": "Output format must be 'json' or 'markdown'."})
        
    # 2. Save file temporarily with a secure, unique name
    import uuid
    safe_filename = f"{uuid.uuid4()}.pdf"
    temp_file_path = os.path.join(TEMP_DIR, safe_filename)
    
    file_bytes = await file.read()
    
    if len(file_bytes) == 0:
        logger.warning(f"0-byte file uploaded: {file.filename}")
        return JSONResponse(status_code=400, content={"success": False, "error": "Empty File", "details": "The uploaded file is empty."})
        
    if not file_bytes.startswith(b"%PDF-"):
        logger.warning(f"File signature mismatch: {file.filename}")
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid File Signature", "details": "The uploaded file is not a valid PDF document."})

    with open(temp_file_path, "wb") as buffer:
        buffer.write(file_bytes)
        
    try:
        # 3. Route to proper extraction method
        if engine == "fast":
            data = PDFParserService.extract_fast_text(temp_file_path)
        elif engine == "structural":
            data = PDFParserService.extract_structural_text(temp_file_path)
        else:
            data = PDFParserService.extract_hybrid_text(temp_file_path)
            
        logger.info(f"Successfully extracted data from {file.filename}")
        
        # 4. Output Formatting
        if output_format == "markdown":
            md_content = json_to_markdown(data)
            return PlainTextResponse(md_content)
            
        return {"success": True, "data": data}
        
    except ValueError as ve:
        logger.warning(f"Validation Error for {file.filename}: {ve}")
        return JSONResponse(status_code=400, content={"success": False, "error": "Bad Request", "details": str(ve)})
    except Exception as e:
        logger.error(f"Internal Error during extraction of {file.filename}: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"success": False, "error": "Extraction Failed", "details": str(e)})
        
    finally:
        # 5. Clean up file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception:
                pass