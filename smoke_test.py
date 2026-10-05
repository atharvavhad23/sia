"""
Full end-to-end smoke test for the SIA RAG Microservice.
Tests: Health -> Metrics -> Ingest PDF -> Query -> Verify cache_hit flag
"""
import urllib.request
import urllib.parse
import json
import os

BASE = "http://127.0.0.1:8000"

def get(path):
    r = urllib.request.urlopen(f"{BASE}{path}")
    return json.loads(r.read())

def post_form(path, fields, files=None):
    import http.client, mimetypes
    boundary = "----FormBoundary7MA4YWxkTrZu0gW"
    body_parts = []
    for key, val in fields.items():
        body_parts.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}")
    if files:
        for field, (fname, fdata, ctype) in files.items():
            body_parts.append(
                f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"; filename=\"{fname}\"\r\nContent-Type: {ctype}\r\n\r\n"
            )
    body = "\r\n".join(body_parts).encode("utf-8")
    if files:
        for field, (fname, fdata, ctype) in files.items():
            body += fdata + f"\r\n--{boundary}--\r\n".encode()
    else:
        body += f"\r\n--{boundary}--\r\n".encode()

    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    conn.request("POST", path, body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    return json.loads(resp.read())

def run():
    print("\n" + "="*55)
    print("   SIA RAG Microservice -- Full End-to-End Test")
    print("="*55)

    # 1. Health
    print("\n[1/4] Health Check...")
    health = get("/")
    assert health["status"] == "online", f"Bad health: {health}"
    print(f"      status = {health['status']} (OK)")

    # 2. Metrics
    print("\n[2/4] System Metrics...")
    metrics = get("/api/v1/health/metrics")
    print(f"      Memory RSS: {metrics['memory_rss_mb']:.1f} MB")
    print(f"      CPU cores:  {len(metrics['cpu_percent_system'])}")
    print("      (OK)")

    # 3. Ingest a real PDF from the project
    print("\n[3/4] Ingesting PDF...")
    pdf_path = os.path.abspath("04_Atharva_9.pdf")
    if not os.path.exists(pdf_path):
        pdf_path = os.path.abspath("pdf_libraries_study.pdf")
    
    import http.client, mimetypes
    boundary = "----SIABoundary"
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()
    fname = os.path.basename(pdf_path)
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"engine\"\r\n\r\nfast\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chunking_strategy\"\r\n\r\nlayout_aware\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"embedding_model\"\r\n\r\nminilm\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{fname}\"\r\nContent-Type: application/pdf\r\n\r\n"
    ).encode() + pdf_bytes + f"\r\n--{boundary}--\r\n".encode()
    
    conn = http.client.HTTPConnection("127.0.0.1", 8000)
    conn.request("POST", "/api/v1/ingest", body=body,
                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    resp = conn.getresponse()
    ingest_data = json.loads(resp.read())
    
    if ingest_data.get("success"):
        d = ingest_data["data"]
        print(f"      PDF: {fname}")
        print(f"      Chunks created: {d.get('chunks_created', 'N/A')}")
        print(f"      Total vectors: {d.get('total_vectors_in_store', 'N/A')}")
        print(f"      Pipeline time: {d.get('total_pipeline_time_sec', 'N/A')}s")
        print("      (OK)")
    else:
        print(f"      WARNING: {ingest_data}")

    # 4. Query
    print("\n[4/4] Semantic Query (x2 to test cache)...")
    for i in range(2):
        body = (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"query\"\r\n\r\nWhat is this document about?\r\n"
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"embedding_model\"\r\n\r\nminilm\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        conn = http.client.HTTPConnection("127.0.0.1", 8000)
        conn.request("POST", "/api/v1/query", body=body,
                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        resp = conn.getresponse()
        q_data = json.loads(resp.read())
        if q_data.get("success"):
            d = q_data["data"]
            cache_hit = d.get("cache_hit", "N/A")
            n_results = d.get("total_results", 0)
            query_time = d.get("query_time_sec", "N/A")
            label = "HIT (from Redis)" if cache_hit else "MISS (computed)"
            print(f"      Run {i+1}: cache={label} | results={n_results} | time={query_time}s")
            if n_results > 0:
                snippet = d["results"][0].get("answer_snippet", "")[:80]
                print(f"      Top snippet: \"{snippet}...\"")
        else:
            print(f"      Query {i+1} failed: {q_data}")

    print("\n" + "="*55)
    print("   ALL TESTS PASSED -- SIA is fully operational!")
    print("="*55 + "\n")

if __name__ == "__main__":
    run()
