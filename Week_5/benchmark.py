import os
import time
import requests
import json
from pathlib import Path

# Assuming API is running locally
API_URL = "http://127.0.0.1:8000/api/v1/extract"
TEST_PDF_DIR = Path("D:/sia-utilities/test_pdfs")

def run_benchmark():
    print("Starting PDF Extraction Benchmark...")
    results = []
    
    if not TEST_PDF_DIR.exists():
        print("Test PDF directory not found.")
        return

    for category_dir in TEST_PDF_DIR.iterdir():
        if category_dir.is_dir():
            for pdf_file in category_dir.glob("*.pdf"):
                start_time = time.time()
                try:
                    with open(pdf_file, "rb") as f:
                        response = requests.post(
                            API_URL,
                            data={"engine": "hybrid", "output_format": "json"},
                            files={"file": (pdf_file.name, f, "application/pdf")}
                        )
                    end_time = time.time()
                    
                    status = "SUCCESS" if response.status_code == 200 else "FAILED"
                    error_msg = "" if status == "SUCCESS" else response.json().get("details", str(response.text))
                    
                    results.append({
                        "file": pdf_file.name,
                        "category": category_dir.name,
                        "time_sec": round(end_time - start_time, 4),
                        "status": status,
                        "error": error_msg
                    })
                except Exception as e:
                    results.append({
                        "file": pdf_file.name,
                        "category": category_dir.name,
                        "time_sec": 0,
                        "status": "FAILED",
                        "error": str(e)
                    })

    print("\n--- Benchmark Results ---")
    for r in results:
        print(f"[{r['status']}] {r['category']}/{r['file']} - {r['time_sec']}s")
        if r['status'] == "FAILED":
            print(f"   Reason: {r['error']}")

    with open("benchmark_report.json", "w") as f:
        json.dump(results, f, indent=4)
        
    print("\nReport saved to benchmark_report.json")

if __name__ == "__main__":
    run_benchmark()
