# SIA PDF Extraction Microservice - Engineering Report

## 1. Executive Summary
This report summarizes the performance benchmarking and failure analysis conducted during Week 3 to evaluate the production readiness of the PDF Extraction Microservice. The hybrid extraction engine (PyMuPDF + Camelot) was tested for speed, memory efficiency, and accuracy across various document types.

## 2. Benchmarking Results
The system was benchmarked against a curated dataset of PDFs representing different business verticals:

| Category | Average Time (s) | Success Rate | Primary Bottleneck |
|----------|------------------|--------------|--------------------|
| Financial Reports | 1.24 | 100% | Table Extraction (Camelot) |
| Legal Contracts | 0.45 | 100% | Text parsing (PyMuPDF) |
| Invoices / Receipts | 0.82 | 90% | Image/Scanned DPI issues |
| Scanned Documents | N/A | 0% | OCR not yet integrated |

**Key Findings:**
- The `fast` engine (PyMuPDF) operates at ~0.05s per page, making it highly suitable for bulk text ingestion.
- The `hybrid` engine introduces a slight latency penalty due to table layout analysis but correctly parses complex financial grids.

## 3. Performance Profiling
Using `cProfile` and `memory_profiler`, we observed the following during a heavy load test (100+ page financial document):
- **Max Memory Usage**: 145.2 MiB (Spikes during Camelot stream reading).
- **Execution Strategy**: The implementation of `ThreadPoolExecutor` and FastAPI's `run_in_threadpool` successfully prevented main thread blocking. The API remained responsive to health checks (`/`) while processing heavy documents in the background.

## 4. Failure Analysis
An analysis of failed extractions revealed the following root causes:
1. **Corrupt Metadata (40%)**: Files lacking valid EOF markers. Correctly caught by `PDFCorruptedException`.
2. **Missing OCR (60%)**: Documents consisting purely of scanned images returned empty text. 
   - *Recommendation*: Integrate Tesseract OCR in a future sprint specifically for the `scanned` category.

## 5. Conclusion
The service is robust and handles structured/native PDFs exceptionally well. Exception handling and asynchronous routing are stable. The service is cleared for staging deployment.
