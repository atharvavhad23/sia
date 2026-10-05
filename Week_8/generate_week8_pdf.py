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
    for label, value in [
        ("Employee Name:", "Atharva Ravikiran Avhad"),
        ("Date:", datetime.datetime.now().strftime("%d/%m/%Y")),
        ("Reporting Manager:", "Aditya Chauhan"),
    ]:
        pdf.set_font("Arial", 'B', 11)
        pdf.cell(50, 7, label, 0, 0)
        pdf.set_font("Arial", '', 11)
        pdf.cell(0, 7, value, 0, 1)

    pdf.ln(5)

    # Work Summary
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Work Summary", 0, 1)
    pdf.set_font("Arial", '', 11)
    summary = (
        "Completed Week 8: Optimization and Engineering Handover -- the final sprint of the SIA RAG "
        "Microservice project. The focus was on transforming 7 weeks of iterative development into a "
        "production-ready, fully documented, and deployable system. Implemented targeted Redis caching "
        "to address the CPU bottleneck identified in Week 7's Locust profiling. Containerized the full "
        "stack with Docker Compose including persistent LanceDB volume mounts, established a CI/CD "
        "pipeline via GitHub Actions, and produced comprehensive engineering handover documentation."
    )
    pdf.multi_cell(0, 6, summary)
    pdf.ln(5)

    # Completed Tasks
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Completed Tasks", 0, 1)

    tasks = [
        (
            "Redis Query Caching (Targeted Optimization):",
            "Implemented a Redis-backed cache service (cache.py) with SHA-256 key design, "
            "TTL-based expiry, and explicit cache invalidation on every document ingest. "
            "Cache hits serve in ~6ms vs ~510ms (85x improvement). Cache benchmark report produced "
            "with honest hit/miss analysis under realistic 60/40 repeated-to-novel query traffic."
        ),
        (
            "Docker Compose Stack:",
            "Authored docker-compose.yml bringing up the FastAPI app, Redis 7, and a named "
            "persistent Docker volume for LanceDB. Configured health checks and depends_on "
            "ordering so Redis is fully healthy before the API accepts connections. Added .env.example "
            "documenting all configurable parameters including worker count and cache TTL."
        ),
        (
            "CI/CD Pipeline (GitHub Actions):",
            "Created .github/workflows/ci.yml that runs on every PR and push: "
            "flake8 lint, black formatting check, Week 3 pytest suite, Docker image build, "
            "and a container smoke test that hits /health to verify the app starts cleanly."
        ),
        (
            "Architecture Diagrams (Mermaid):",
            "Produced three version-controlled Mermaid diagrams: (1) System/component diagram, "
            "(2) Query request sequence diagram (cache -> embedding -> LanceDB -> extractive QA), "
            "(3) Ingestion flow diagram (PDF upload -> parse -> chunk -> embed -> store -> cache purge)."
        ),
        (
            "Deployment Guide:",
            "Authored a standalone Deployment_Guide.md assuming zero prior context, covering "
            "prerequisites, environment variables, Docker Compose steps, health verification, "
            "scaling guidance from Week 7 capacity data, and a troubleshooting section for "
            "real failure modes encountered during development."
        ),
        (
            "README Audit & Rewrite:",
            "Completely rewrote README.md to remove all FAISS references (migrated in Week 5), "
            "reflect the current LanceDB + Redis stack, and include setup instructions, "
            "environment variables, running tests, and scaling guidance with Week 7 numbers."
        ),
        (
            "Final Engineering Report:",
            "Produced Final_Engineering_Report.md covering all 8 weeks with evidence-based "
            "decisions, Week 6 retrieval benchmark data, Week 7 load test numbers, and "
            "Week 8 caching results. Identifies known limitations and next steps."
        ),
        (
            "Project Presentation:",
            "Structured a 9-slide Project_Presentation.md narrative document for non-technical "
            "stakeholders covering: problem statement, architecture, evolution (FAISS to LanceDB), "
            "retrieval bake-off, load testing findings, optimization results, and future roadmap."
        ),
    ]

    for title, detail in tasks:
        pdf.ln(3)
        pdf.set_font("Arial", 'B', 11)
        pdf.multi_cell(0, 6, f"- {title}")
        pdf.set_font("Arial", '', 11)
        pdf.multi_cell(0, 6, f"  {detail}")

    pdf.ln(5)

    # Next Steps
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, "Next Steps", 0, 1)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 6,
        "The SIA RAG Microservice is now production-ready for a local-first deployment. "
        "The logical next step is Week 9: LLM integration -- connecting Gemini or Groq to generate "
        "synthesized natural language answers from the retrieved context, transitioning from "
        "extractive to generative RAG."
    )

    output_path = "Daily_Work_Report_Week8.pdf"
    pdf.output(output_path)
    print(f"Generated {output_path}")

if __name__ == "__main__":
    generate_report()
