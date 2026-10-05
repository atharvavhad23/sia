from locust import HttpUser, task, between
import random
import json

QUERIES = [
    "What is NexaShield?",
    "How does the AI anomaly detection work?",
    "Summarize the main objectives.",
    "What are the skills used in this project?",
    "Explain the methodology for the real estate predictor.",
    "Is there any reference to Koyna wildlife sanctuary?",
    "Who authored this document?",
    "What is the email address?",
    "Tell me about the tech stack.",
    "What is the system architecture?"
]

class QueryOnlyUser(HttpUser):
    # Wait time between requests (simulating think time)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts. We'll make sure the system is healthy."""
        self.client.get("/api/v1/health/metrics", name="/api/v1/health/metrics")

    @task(3)
    def cached_query(self):
        """Simulate a frequent/cached query"""
        query = QUERIES[0]  # Hardcode one query that gets repeated often
        payload = {"query": query, "embedding_model": "minilm"}
        self.client.post("/api/v1/query", data=payload, name="/api/v1/query (Cached)")

    @task(7)
    def novel_query(self):
        """Simulate a mix of random queries"""
        query = random.choice(QUERIES)
        payload = {"query": query, "embedding_model": "minilm"}
        self.client.post("/api/v1/query", data=payload, name="/api/v1/query (Novel)")
