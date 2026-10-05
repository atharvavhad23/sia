from locust import HttpUser, task, between
import random
import os
from pathlib import Path

QUERIES = [
    "What is NexaShield?",
    "How does the AI anomaly detection work?",
    "Summarize the main objectives.",
    "What are the skills used in this project?",
    "Explain the methodology for the real estate predictor.",
]

# Find a dummy PDF to upload
DUMMY_PDF_PATH = Path(__file__).parent.parent.parent / "Week_5" / "temp_docs" / "b70892a7-3d21-476f-9319-a61233432f5c.pdf"

class MixedLoadUser(HttpUser):
    wait_time = between(1, 4)

    @task(9)
    def search_query(self):
        """90% of requests are queries"""
        query = random.choice(QUERIES)
        payload = {"query": query, "embedding_model": "minilm"}
        self.client.post("/api/v1/query", data=payload, name="/api/v1/query")

    @task(1)
    def ingest_document(self):
        """10% of requests are heavy document ingestions"""
        if DUMMY_PDF_PATH.exists():
            with open(DUMMY_PDF_PATH, "rb") as f:
                files = {"file": ("test_doc.pdf", f, "application/pdf")}
                data = {"engine": "fast", "chunking_strategy": "recursive", "embedding_model": "minilm"}
                
                # Use a larger timeout for ingestion as it is CPU bound
                self.client.post("/api/v1/ingest", data=data, files=files, name="/api/v1/ingest", timeout=60)
        else:
            # Fallback to health check if file not found to keep the ratio roughly accurate
            self.client.get("/api/v1/health/metrics", name="/api/v1/health/metrics (Fallback)")
