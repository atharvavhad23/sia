from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Daily Work Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

def generate_report():
    pdf = PDF()
    pdf.add_page()
    pdf.set_font("Arial", size=11)
    
    # Metadata
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 7, "Employee Name:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 7, "Atharva Ravikiran Avhad", 0, 1)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 7, "Date:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 7, "24/07/2026", 0, 1)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(40, 7, "Reporting Manager:", 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 7, "Aditya Chauhan", 0, 1)
    
    pdf.ln(5)
    
    # Work Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Work Summary", 0, 1)
    pdf.set_font("Arial", '', 11)
    summary = (
        "Started Week 3 objectives focusing on transforming the PDF extraction service into a "
        "production-ready microservice. Successfully established a comprehensive automated "
        "testing framework to prevent regressions. Additionally, enhanced the application's "
        "stability and observability by implementing custom domain-specific exception handling, "
        "structured JSON logging, and threadpool-based asynchronous processing to handle "
        "heavy PDF extractions without blocking the main event loop."
    )
    pdf.multi_cell(0, 6, summary)
    pdf.ln(5)
    
    # Completed Tasks
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Completed Tasks", 0, 1)
    pdf.set_font("Arial", '', 11)
    tasks = [
        "Automated Test Suite (Unit & API): Wrote and executed 14 tests using pytest and FastAPI's TestClient, covering edge cases like empty uploads, invalid extensions, corrupted files, and zero-page PDFs. All tests passed successfully.",
        "Structured Error Handling: Created custom exception classes (PDFCorruptedException, PDFPasswordProtectedException) to provide cleaner, more specific error routing within the microservice.",
        "Asynchronous Processing: Integrated FastAPI's run_in_threadpool to push CPU-heavy extraction tasks into background threads, preventing HTTP request blocking.",
        "Structured JSON Logging: Implemented a custom JSON formatter for the system logger to allow seamless integration with centralized production logging systems."
    ]
    for task in tasks:
        pdf.multi_cell(0, 6, f"- {task}")
        pdf.ln(2)
    pdf.ln(3)
    
    # Pending Tasks
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Pending Tasks", 0, 1)
    pdf.set_font("Arial", '', 11)
    pending = [
        "Benchmark extraction pipeline using 10 different PDF categories.",
        "Analyze extraction failures and classify root causes.",
        "Profile system performance (CPU, RAM, Execution Time).",
        "Optimize extraction pipeline based on profiling metrics.",
        "Prepare final engineering reports (Performance Profiling, Failure Analysis, Production Readiness Checklist)."
    ]
    for p in pending:
        pdf.multi_cell(0, 6, f"- {p}")
    pdf.ln(5)
    
    # Plan for Tomorrow
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Plan for Tomorrow", 0, 1)
    pdf.set_font("Arial", '', 11)
    plan = [
        "Curate a dataset of 10 diverse PDFs (financial, legal, invoices, etc.) and write a benchmarking script to process them.",
        "Record success rates, extraction accuracy, and processing times.",
        "Perform failure analysis on any failed extractions and classify the root causes for the engineering report."
    ]
    for p in plan:
        pdf.multi_cell(0, 6, f"- {p}")
    pdf.ln(8)
    
    # Declaration
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Employee Declaration", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6, "I hereby confirm that the above information accurately represents the work completed by me on the mentioned date.")
    pdf.ln(10)
    
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 6, "Employee Signature:", 0, 1)
    pdf.ln(8)
    pdf.cell(0, 6, "___________________________", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 6, "Atharva Ravikiran Avhad", 0, 1)
    
    out_name = "Daily_Work_Report_24_07_2026.pdf"
    pdf.output(out_name)
    print(f"Generated {out_name}")

if __name__ == "__main__":
    generate_report()
