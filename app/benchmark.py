import sys
sys.stdout.reconfigure(encoding='utf-8')
import time
import os
import glob
import fitz         # PyMuPDF
import pdfplumber
import pandas as pd

class PDFBenchmarkEngine:
    def __init__(self, target_dir: str):
        self.target_dir = target_dir
        self.pdf_files = glob.glob(os.path.join(target_dir, '**', '*.pdf'), recursive=True)
        if not self.pdf_files:
            print(f"⚠️ No PDFs found in '{target_dir}'. Please add some PDF files to test.")

    def run_pymupdf(self, file_path: str):
        start_time = time.time()
        char_count = 0
        success = False
        try:
            with fitz.open(file_path) as doc:
                for page in doc:
                    char_count += len(page.get_text())
            success = True
        except Exception as e:
            pass
        elapsed = time.time() - start_time
        return {"Latency": elapsed, "Success": success}

    def run_pdfplumber(self, file_path: str):
        start_time = time.time()
        table_count = 0
        success = False
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    tables = page.extract_tables()
                    table_count += len(tables)
            success = True
        except Exception as e:
            pass
        elapsed = time.time() - start_time
        return {"Latency": elapsed, "Success": success}

    def run_camelot(self, file_path: str):
        start_time = time.time()
        table_count = 0
        success = False
        try:
            import camelot
            tables = camelot.read_pdf(file_path, pages='all', flavor='stream', suppress_stdout=True)
            table_count = len(tables)
            success = True
        except Exception as e:
            pass
        elapsed = time.time() - start_time
        return {"Latency": elapsed, "Success": success}

    def run_hybrid_camelot_pymupdf(self, file_path: str):
        start_time = time.time()
        success = False
        try:
            import camelot
            try:
                camelot.read_pdf(file_path, pages='all', flavor='stream', suppress_stdout=True)
            except Exception:
                pass
            with fitz.open(file_path) as doc:
                for page in doc:
                    page.get_text()
            success = True
        except Exception:
            pass
        return {"Latency": time.time() - start_time, "Success": success}

    def run_hybrid_camelot_pdfplumber(self, file_path: str):
        start_time = time.time()
        success = False
        try:
            import camelot
            try:
                camelot.read_pdf(file_path, pages='all', flavor='stream', suppress_stdout=True)
            except Exception:
                pass
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page.extract_text()
            success = True
        except Exception:
            pass
        return {"Latency": time.time() - start_time, "Success": success}

    def run_hybrid_pdfplumber_pymupdf(self, file_path: str):
        start_time = time.time()
        success = False
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page.extract_tables()
            with fitz.open(file_path) as doc:
                for page in doc:
                    page.get_text()
            success = True
        except Exception:
            pass
        return {"Latency": time.time() - start_time, "Success": success}

    def execute_all(self):
        if not self.pdf_files:
            return
            
        print(f"🔬 Found {len(self.pdf_files)} PDFs for benchmarking in '{self.target_dir}'\n")
        results = []
        
        for file_path in self.pdf_files:
            file_name = os.path.basename(file_path)
            category = os.path.basename(os.path.dirname(file_path)) 
            if category == os.path.basename(self.target_dir):
                category = "General"
                
            print(f"🔄 Processing: {file_name} [{category}]")
            
            mupdf = self.run_pymupdf(file_path)
            plumb = self.run_pdfplumber(file_path)
            cam = self.run_camelot(file_path)
            h1 = self.run_hybrid_camelot_pymupdf(file_path)
            h2 = self.run_hybrid_camelot_pdfplumber(file_path)
            h3 = self.run_hybrid_pdfplumber_pymupdf(file_path)
            
            results.append({
                "Document": file_name[:12],
                "PyMuPDF": round(mupdf["Latency"], 3) if mupdf["Success"] else "Fail",
                "pdfplumber": round(plumb["Latency"], 3) if plumb["Success"] else "Fail",
                "Camelot": round(cam["Latency"], 3) if cam["Success"] else "Fail",
                "H1(Cam+MuPDF)": round(h1["Latency"], 3) if h1["Success"] else "Fail",
                "H2(Cam+plumb)": round(h2["Latency"], 3) if h2["Success"] else "Fail",
                "H3(plumb+Mu)": round(h3["Latency"], 3) if h3["Success"] else "Fail"
            })

        df = pd.DataFrame(results)
        
        print("\n========================= EXTENDED LATENCY MATRIX (Seconds) =========================")
        print(df.to_string(index=False))
        print("=====================================================================================\n")
        return df

if __name__ == "__main__":
    TEST_DIR = "test_pdfs"
    benchmarker = PDFBenchmarkEngine(TEST_DIR)
    benchmarker.execute_all()