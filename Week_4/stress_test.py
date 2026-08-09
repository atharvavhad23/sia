import fitz
import time
import requests
import os

def create_massive_pdf(filename, pages=50):
    print(f"Generating a {pages}-page massive PDF...")
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page()
        page.insert_text((50, 50), f"This is page {i+1} of the massive stress test document.")
        # Insert a pseudo table
        page.insert_text((50, 100), "Column A | Column B | Column C")
        page.insert_text((50, 120), "100 | 200 | 300")
    doc.save(filename)
    doc.close()
    print("PDF generated successfully.")

def run_stress_test(filename, engine):
    url = "http://127.0.0.1:8000/api/v1/extract"
    data = {"engine": engine, "output_format": "json"}
    print(f"\n--- Starting benchmark for '{engine}' engine ---")
    start_time = time.time()
    with open(filename, "rb") as f:
        response = requests.post(url, data=data, files={"file": (filename, f, "application/pdf")})
    end_time = time.time()
    
    latency = end_time - start_time
    if response.status_code == 200:
        result = response.json()
        print(f"SUCCESS: {engine} engine extracted {len(result['data'].get('pages', []))} pages in {latency:.2f} seconds.")
    else:
        print(f"FAILED: {engine} returned {response.status_code} - {response.text}")

if __name__ == "__main__":
    TEST_PDF = "massive_stress_test.pdf"
    create_massive_pdf(TEST_PDF, pages=50)
    
    # We assume the API server is running locally on port 8000
    try:
        run_stress_test(TEST_PDF, "fast")
        run_stress_test(TEST_PDF, "structural")
        run_stress_test(TEST_PDF, "hybrid")
    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to API. Please ensure the backend is running.")
        
    if os.path.exists(TEST_PDF):
        os.remove(TEST_PDF)
