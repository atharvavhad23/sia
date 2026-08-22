import cProfile
import pstats
import io
import memory_profiler
from app.services.pdfparser import PDFParserService
from pathlib import Path
import logging

# Disable unnecessary logging for clean profiling output
logging.getLogger("sia.pdfparser").setLevel(logging.ERROR)

def profile_extraction(pdf_path):
    print(f"--- Profiling extraction for {pdf_path.name} ---")
    
    # 1. CPU and Execution Time Profiling
    print("Running cProfile (Execution Time & Function Calls)...")
    pr = cProfile.Profile()
    pr.enable()
    
    try:
        # Simulate the hybrid extraction pipeline
        PDFParserService.extract_hybrid_text(str(pdf_path))
    except Exception as e:
        print(f"Extraction failed: {e}")
        
    pr.disable()
    s = io.StringIO()
    sortby = 'cumulative'
    ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
    ps.print_stats(15)  # Print top 15 time-consuming functions
    print(s.getvalue())

    # 2. Memory Profiling
    print("Running Memory Profiler...")
    try:
        mem_usage = memory_profiler.memory_usage((PDFParserService.extract_hybrid_text, (str(pdf_path),)))
        print(f"Maximum Memory Usage: {max(mem_usage):.2f} MiB")
        print(f"Minimum Memory Usage: {min(mem_usage):.2f} MiB")
    except Exception as e:
        print(f"Memory profiling failed: {e}")

if __name__ == "__main__":
    TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")
    financial_pdf = TEST_PDF_DIR / "financial" / "q3_report.pdf"
    
    if financial_pdf.exists():
        profile_extraction(financial_pdf)
    else:
        print(f"Could not find test PDF at {financial_pdf}")
