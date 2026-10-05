from fpdf import FPDF
import datetime

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
    date_str = datetime.datetime.now().strftime("%d/%m/%Y")
    pdf.cell(0, 7, date_str, 0, 1)
    
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
        "Started Week 7 objectives focusing on Scalability and Infrastructure Testing. "
        "Successfully established a comprehensive load testing suite using Locust to evaluate "
        "system performance under heavy concurrency (100, 500, and 1000 users). "
        "Added system instrumentation via psutil to track CPU and Memory metrics in real-time. "
        "Conducted deep bottleneck analysis exposing the limitations of the Python GIL during "
        "heavy PDF ingestion and embedding generation."
    )
    pdf.multi_cell(0, 6, summary)
    pdf.ln(5)
    
    # Completed Tasks
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Completed Tasks", 0, 1)
    pdf.set_font("Arial", '', 11)
    
    tasks = [
        "Load Testing Suite: Built Locust scripts (locustfile_query.py and locustfile_mixed.py) to simulate semantic search and heavy document ingestion workloads.",
        "System Instrumentation: Injected an API middleware to track latency and added /api/v1/health/metrics to expose real-time CPU and Memory usage.",
        "Automated Execution & Plotting: Wrote Python scripts to automatically execute Locust across multiple concurrency tiers and plot throughput/latency charts using pandas and matplotlib.",
        "Bottleneck Analysis: Identified that CPU starvation (via the GIL) from sentence-transformers and PyMuPDF causes severe latency degradation at scale.",
        "Capacity Planning: Authored a comprehensive scaling document recommending horizontal Uvicorn scaling, Redis caching, and a Celery queue for ingestion."
    ]
    
    for task in tasks:
        pdf.set_font("Arial", 'B', 14)
        pdf.cell(5, 6, "-", 0, 0)
        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, task)
        pdf.ln(2)
        
    pdf.ln(3)
    
    # Next Steps
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Next Steps / Blockers", 0, 1)
    pdf.set_font("Arial", '', 11)
    next_steps = (
        "Prepare for Week 8 by implementing the infrastructure recommendations, specifically "
        "migrating the PDF ingestion pipeline to a background message queue (e.g., Celery) "
        "to prevent it from blocking semantic search queries."
    )
    pdf.multi_cell(0, 6, next_steps)
    
    # Save the PDF
    output_filename = f"Daily_Work_Report_Week7.pdf"
    pdf.output(output_filename)
    print(f"Generated {output_filename}")

if __name__ == "__main__":
    generate_report()
