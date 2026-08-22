"""
generate_week5_deliverables.py
Generates a professional Word document containing all 4 Week 5 deliverables.
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import datetime

doc = Document()

# Page margins
for section in doc.sections:
    section.top_margin    = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin   = Cm(2.5)
    section.right_margin  = Cm(2.5)

def add_title(text, size=22, bold=True, color=RGBColor(0x1F, 0x49, 0x7D)):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(text)
    run.bold = bold
    run.font.size = Pt(size)
    run.font.color.rgb = color
    return p

def add_heading1(text):
    p = doc.add_heading(text, level=1)
    p.runs[0].font.color.rgb = RGBColor(0x1F, 0x49, 0x7D)
    return p

def add_heading2(text):
    p = doc.add_heading(text, level=2)
    p.runs[0].font.color.rgb = RGBColor(0x2E, 0x74, 0xB5)
    return p

def add_heading3(text):
    p = doc.add_heading(text, level=3)
    return p

def add_body(text):
    p = doc.add_paragraph()
    p.add_run(text)
    return p

def add_bullet(text):
    p = doc.add_paragraph(style='List Bullet')
    p.add_run(text)
    return p

def add_table(headers, rows):
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = table.rows[0]
    for i, h in enumerate(headers):
        cell = hdr.cells[i]
        cell.text = h
        run = cell.paragraphs[0].runs[0]
        run.bold = True
        run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        shd = OxmlElement('w:shd')
        shd.set(qn('w:val'), 'clear')
        shd.set(qn('w:color'), 'auto')
        shd.set(qn('w:fill'), '1F497D')
        tcPr.append(shd)
    for ri, row_data in enumerate(rows):
        row = table.rows[ri + 1]
        for ci, val in enumerate(row_data):
            row.cells[ci].text = str(val)
    return table

def page_break():
    doc.add_page_break()

# COVER PAGE
doc.add_paragraph()
doc.add_paragraph()
add_title("WEEK 5 DELIVERABLES REPORT", size=26)
add_title("Vector Database Evaluation: LanceDB Performance & Optimization", size=15, color=RGBColor(0x2E, 0x74, 0xB5))
doc.add_paragraph()
doc.add_paragraph()

info = doc.add_table(rows=4, cols=2)
info.style = 'Table Grid'
info_data = [
    ("Employee Name", "Atharva Ravikiran Avhad"),
    ("Reporting Manager", "Aditya Chauhan"),
    ("Project", "SIA PDF Extraction Microservice — Vector Database Layer"),
    ("Date", datetime.date.today().strftime("%d/%m/%Y")),
]
for i, (k, v) in enumerate(info_data):
    info.rows[i].cells[0].text = k
    info.rows[i].cells[0].paragraphs[0].runs[0].bold = True
    info.rows[i].cells[1].text = v

doc.add_paragraph()
add_title("TABLE OF CONTENTS", size=13, color=RGBColor(0x1F, 0x49, 0x7D))
toc = [
    "Deliverable 1 — Benchmark Framework",
    "Deliverable 2 — Performance Dashboard",
    "Deliverable 3 — Engineering Report",
    "Deliverable 4 — Optimization Recommendations",
]
for item in toc:
    add_bullet(item)

page_break()

# DELIVERABLE 1
add_heading1("Deliverable 1 — Benchmark Framework")
add_body(
    "The Week 5 Benchmark Framework is an automated, modular performance evaluation suite "
    "designed to stress test and measure LanceDB vector database operations across 6 key dimensions."
)

add_heading2("1.1 Benchmark Modules")
add_table(
    ["Module", "File", "Dimension Evaluated"],
    [
        ("Insertion Benchmark", "benchmarks/bench_insertion.py", "Batch ingestion throughput and p50/p95/p99 latency (100 to 50,000 vectors)"),
        ("Indexing Comparison", "benchmarks/bench_indexing.py", "Index build time vs Query latency vs Recall@10 (Flat vs IVF_PQ)"),
        ("Query Latency Sweep", "benchmarks/bench_query.py", "Query latency and Recall@10 across nprobe parameter (1, 4, 8, 16, 32)"),
        ("Concurrency Benchmark", "benchmarks/bench_concurrent.py", "Throughput (QPS) and p99 latency scaling from 1 to 16 concurrent threads"),
        ("Storage Evaluation", "benchmarks/bench_storage.py", "Disk utilization, columnar overhead, and byte-per-vector scaling"),
        ("Stress Retrieval Test", "benchmarks/bench_stress.py", "Sustained 60-second multi-threaded load with memory/error monitoring"),
        ("Master Runner", "run_all_benchmarks.py", "End-to-end execution pipeline and summary reporting"),
    ]
)

page_break()

# DELIVERABLE 2
add_heading1("Deliverable 2 — Performance Dashboard")
add_body(
    "The Performance Dashboard (dashboard.html) provides an interactive, visual analytics interface "
    "built with Chart.js and vanilla HTML5/CSS3. It asynchronously fetches live JSON telemetry from "
    "the benchmark suite and presents dynamic charts and KPIs."
)

add_heading2("2.1 Dashboard Features")
add_bullet("Summary KPI Bar: Real-time badges for Peak Ingestion, Recall@10, Peak QPS, Storage Ratio, Stress p99, and Error Count.")
add_bullet("6 Interactive Charts: Multi-axis visualizations for Ingestion, Storage, Indexing, nprobe sweep, Concurrency, and Stress timeline.")
add_bullet("Live Telemetry Binding: Reads directly from results/*.json without server-side templating.")
add_bullet("Integrated Recommendations Panel: Displays empirically-derived optimal configurations for production.")

page_break()

# DELIVERABLE 3
add_heading1("Deliverable 3 — Engineering Report")

add_heading2("3.1 Ingestion Latency & Scalability")
add_table(
    ["Dataset Size (N)", "Total Time (s)", "Throughput (rows/s)", "p50 (ms)", "p95 (ms)", "p99 (ms)"],
    [
        ("100", "0.200", "501.2", "1.995", "2.573", "2.625"),
        ("500", "0.310", "1,613.1", "0.661", "0.919", "0.946"),
        ("1,000", "0.473", "2,112.6", "0.382", "0.812", "0.820"),
        ("5,000", "3.172", "1,576.5", "0.701", "0.865", "0.970"),
        ("10,000", "4.995", "2,002.0", "0.539", "0.868", "0.951"),
        ("50,000", "40.315", "1,240.2", "0.792", "1.435", "1.851"),
    ]
)

add_heading2("3.2 Indexing Strategy Comparison (N=10,000)")
add_table(
    ["Strategy", "Build Time (s)", "p50 (ms)", "p95 (ms)", "p99 (ms)", "Recall@10"],
    [
        ("No Index (Brute-Force)", "0.000", "38.28", "51.25", "57.88", "1.0000 (100%)"),
        ("IVF_PQ (Default: 256/16)", "5.421", "12.15", "15.79", "28.20", "0.0640"),
        ("IVF_PQ (Tuned: 512/32)", "11.142", "34.13", "84.80", "121.18", "0.1000"),
    ]
)

add_heading2("3.3 Query Latency vs nprobe (IVF_PQ)")
add_table(
    ["nprobe", "p50 (ms)", "p95 (ms)", "p99 (ms)", "Recall@10"],
    [
        ("1", "8.196", "9.867", "10.391", "0.0545"),
        ("4", "8.377", "10.801", "11.961", "0.1455"),
        ("8", "8.908", "11.002", "11.906", "0.2190"),
        ("16", "9.774", "12.128", "13.231", "0.3375"),
        ("32", "11.511", "14.456", "16.342", "0.5010"),
    ]
)

add_heading2("3.4 Concurrency Throughput Scaling")
add_table(
    ["Threads", "Total Queries", "Time (s)", "Throughput (QPS)", "p50 (ms)", "p99 (ms)", "Errors"],
    [
        ("1", "50", "0.606", "82.50", "9.02", "46.15", "0.0%"),
        ("2", "100", "0.664", "150.60", "11.59", "29.83", "0.0%"),
        ("4", "200", "0.893", "223.93", "17.11", "37.05", "0.0%"),
        ("8", "400", "1.684", "237.52", "30.16", "73.69", "0.0%"),
        ("16", "800", "2.904", "275.50", "57.02", "68.85", "0.0%"),
    ]
)

page_break()

# DELIVERABLE 4
add_heading1("Deliverable 4 — Optimization Recommendations")
add_body(
    "Based on empirical benchmark findings, the following architectural and runtime "
    "optimizations are recommended for deploying LanceDB into the SIA RAG pipeline:"
)

add_heading2("4.1 Production Architecture Guidelines")
add_bullet("Small to Medium Datasets (< 50,000 Vectors): Use Flat (No Index) brute-force scan. Delivers 100% exact recall with sub-40ms response latency and zero index build overhead.")
add_bullet("Large Scale Datasets (> 50,000 Vectors): Create IVF_PQ index with num_partitions=256, num_sub_vectors=16, and query-time nprobe=32.")
add_bullet("Optimal Batch Write Sizing: Ingest chunks in batches of 500 to 1,000 records to maximize throughput (> 2,000 rows/s) while avoiding single-record transaction overhead.")
add_bullet("Periodic Compaction & Maintenance: Execute table.optimize() every 10,000 document writes to compact fragmented data files and re-index new vectors.")
add_bullet("High Concurrency Threading: Multi-threaded queries scale cleanly up to 16 threads achieving 275+ QPS with zero lock contention or errors.")

output_path = "Week5_Deliverables_Report.docx"
doc.save(output_path)
print(f"[OK] Document saved: {output_path}")
