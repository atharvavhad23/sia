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

import json
from fastapi.concurrency import run_in_threadpool

# Setup Structured JSON Logging
class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_record = {
            "time": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "name": record.name
        }
        if record.exc_info:
            log_record["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(log_record)

logger = logging.getLogger("sia.api")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
# Clear any basic config that might interfere
logger.propagate = False


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
        # 3. Route to proper extraction method (Run asynchronously in threadpool to prevent blocking)
        if engine == "fast":
            data = await run_in_threadpool(PDFParserService.extract_fast_text, temp_file_path)
        elif engine == "structural":
            data = await run_in_threadpool(PDFParserService.extract_structural_text, temp_file_path)
        else:
            data = await run_in_threadpool(PDFParserService.extract_hybrid_text, temp_file_path)
            
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


# =============================================================
# Week 4 — RAG Pipeline Endpoints (additive, non-breaking)
# =============================================================

@app.post(
    "/api/v1/ingest",
    tags=["RAG Pipeline"],
    summary="Ingest a PDF into the RAG vector store",
)
async def ingest_pdf(
    engine: str = Form("fast", description="Extraction engine: 'fast', 'structural', 'hybrid'"),
    chunking_strategy: str = Form("recursive", description="Chunking strategy: 'fixed', 'recursive', 'semantic', 'layout_aware'"),
    embedding_model: str = Form("minilm", description="Embedding model: 'minilm', 'bge', 'e5'"),
    file: UploadFile = File(..., description="PDF to ingest into the vector store"),
):
    """
    **Full RAG ingestion pipeline:**
    Upload PDF → Extract → Chunk → Embed → Store in FAISS vector store.

    Returns chunk count, timing per stage, and a document_id for tracing.
    """
    from app.services.rag_pipeline import ingest_document

    logger.info(f"Ingest request: file={file.filename}, engine={engine}, strategy={chunking_strategy}, model={embedding_model}")

    if not file.filename.endswith(".pdf"):
        return JSONResponse(status_code=400, content={"success": False, "error": "Only .pdf files are supported."})
    if engine not in ["fast", "structural", "hybrid"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid engine. Choose: fast, structural, hybrid."})
    if chunking_strategy not in ["fixed", "recursive", "semantic", "layout_aware"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid chunking_strategy."})
    if embedding_model not in ["minilm", "bge", "e5"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid embedding_model. Choose: minilm, bge, e5."})

    import uuid as _uuid
    safe_name = f"{_uuid.uuid4()}.pdf"
    temp_path = os.path.join(TEMP_DIR, safe_name)

    file_bytes = await file.read()
    if len(file_bytes) == 0:
        return JSONResponse(status_code=400, content={"success": False, "error": "Empty file uploaded."})
    if not file_bytes.startswith(b"%PDF-"):
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid PDF signature."})

    with open(temp_path, "wb") as buf:
        buf.write(file_bytes)

    try:
        result = await run_in_threadpool(
            ingest_document,
            temp_path,
            file.filename,
            chunking_strategy,
            embedding_model,
            engine,
        )
        logger.info(f"Ingest complete: {result['chunks_created']} chunks for {file.filename}")
        return {"success": True, "data": result}
    except ValueError as ve:
        logger.warning(f"Ingest validation error for {file.filename}: {ve}")
        return JSONResponse(status_code=400, content={"success": False, "error": str(ve)})
    except Exception as e:
        logger.error(f"Ingest failed for {file.filename}: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"success": False, "error": "Ingest pipeline failed.", "details": str(e)})
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post(
    "/api/v1/query",
    tags=["RAG Pipeline"],
    summary="Query the RAG vector store",
)
async def query_store(
    query: str = Form(..., description="Natural language question to search for"),
    embedding_model: str = Form("minilm", description="Must match model used during ingest: 'minilm', 'bge', 'e5'"),
    top_k: int = Form(5, description="Number of top results to return (1–20)"),
    filter_strategy: str = Form("", description="Optional: filter by chunking strategy"),
    filter_chunk_type: str = Form("", description="Optional: filter by chunk type (text/table/heading)"),
):
    """
    **Retrieve top-k relevant chunks** from the vector store for a given query.

    Embeds the query → cosine similarity search → optional metadata filter → returns results.
    """
    from app.services.rag_pipeline import query_documents

    if not query.strip():
        return JSONResponse(status_code=400, content={"success": False, "error": "Query cannot be empty."})
    if embedding_model not in ["minilm", "bge", "e5"]:
        return JSONResponse(status_code=400, content={"success": False, "error": "Invalid embedding_model."})
    top_k = max(1, min(top_k, 20))

    try:
        result = await run_in_threadpool(
            query_documents,
            query,
            embedding_model,
            top_k,
            filter_strategy if filter_strategy else None,
            filter_chunk_type if filter_chunk_type else None,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"Query failed: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"success": False, "error": "Query failed.", "details": str(e)})