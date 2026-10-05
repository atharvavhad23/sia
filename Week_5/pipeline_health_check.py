"""
pipeline_health_check.py
========================
End-to-end test of every stage in the RAG pipeline:
  1. Server health
  2. Reset vector store
  3. PDF ingestion (using a mini synthetic PDF)
  4. Chunk quality inspection
  5. Query retrieval accuracy
  6. Match percentage validation
"""

import io
import json
import sys
import time
import textwrap
import urllib.request
import urllib.parse
import urllib.error

BASE = "http://127.0.0.1:8000"
PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results = []

def check(name, ok, detail=""):
    icon = PASS if ok else FAIL
    msg = f"{icon}  {name}"
    if detail:
        msg += f"\n      {detail}"
    print(msg)
    results.append((name, ok))

def post_form(url, fields, file_field=None, file_bytes=None, file_name=None):
    """Multipart form POST without requests dependency."""
    boundary = b"----BoundaryXYZ123"
    body = b""
    for k, v in fields.items():
        body += b"--" + boundary + b"\r\n"
        body += f'Content-Disposition: form-data; name="{k}"\r\n\r\n'.encode()
        body += v.encode() + b"\r\n"
    if file_field and file_bytes:
        body += b"--" + boundary + b"\r\n"
        body += f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"\r\n'.encode()
        body += b"Content-Type: application/pdf\r\n\r\n"
        body += file_bytes + b"\r\n"
    body += b"--" + boundary + b"--\r\n"
    content_type = b"multipart/form-data; boundary=" + boundary
    req = urllib.request.Request(url, data=body,
                                 headers={"Content-Type": content_type.decode()},
                                 method="POST")
    resp = urllib.request.urlopen(req, timeout=60)
    return json.loads(resp.read().decode())

def make_synthetic_pdf():
    """Create a tiny valid PDF with known content using only stdlib."""
    content = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>endobj
4 0 obj<</Length 350>>
stream
BT
/F1 12 Tf
50 750 Td
(NexaShield: Forensic-Grade Deepfake Detection System) Tj
0 -20 Td
(NexaShield is a dual-stream deep learning pipeline that uses spatial CNNs) Tj
0 -20 Td
(and DCT spectral analysis to detect AI-generated image and video manipulations.) Tj
0 -20 Td
(It integrates Explainable AI via Grad-CAM to generate visual tampering heatmaps.) Tj
0 -20 Td
(Key Skills: PyTorch, OpenCV, Deep Learning, CNNs, Grad-CAM) Tj
0 -20 Td
(Team Size: 1   Duration: Jan 2026 - Jun 2026) Tj
ET
endstream
endobj
5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
xref
0 6
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000266 00000 n 
0000000668 00000 n 
trailer<</Size 6/Root 1 0 R>>
startxref
749
%%EOF"""
    return content

print("\n" + "="*60)
print("  🔬 SIA RAG PIPELINE — FULL HEALTH CHECK")
print("="*60 + "\n")

# ─── Stage 1: Server Health ──────────────────────────────────
print("📡 STAGE 1: Server Health")
print("-" * 40)
try:
    resp = urllib.request.urlopen(f"{BASE}/", timeout=5)
    data = json.loads(resp.read().decode())
    check("Server responding", resp.status == 200, f"status={data.get('status')}, service={data.get('service')}")
except Exception as e:
    check("Server responding", False, str(e))
    print("\n❌ Server is DOWN. Start it with: python -m uvicorn app.main:app --reload")
    sys.exit(1)

# ─── Stage 2: Reset Vector Store ─────────────────────────────
print("\n🗑️  STAGE 2: Reset Vector Store")
print("-" * 40)
try:
    req = urllib.request.Request(f"{BASE}/api/v1/reset", data=b"", method="POST")
    resp = urllib.request.urlopen(req, timeout=10)
    data = json.loads(resp.read().decode())
    check("Vector store reset", data.get("success") is True, data.get("message", ""))
except Exception as e:
    check("Vector store reset", False, str(e))

# ─── Stage 3: Ingest Synthetic PDF ───────────────────────────
print("\n📥 STAGE 3: PDF Ingestion Pipeline")
print("-" * 40)
pdf_bytes = make_synthetic_pdf()
ingest_result = None
try:
    t0 = time.time()
    ingest_result = post_form(
        f"{BASE}/api/v1/ingest",
        {"engine": "fast", "chunking_strategy": "layout_aware", "embedding_model": "minilm"},
        file_field="file",
        file_bytes=pdf_bytes,
        file_name="nexashield_test.pdf"
    )
    elapsed = round(time.time() - t0, 2)
    ok = ingest_result.get("success") is True
    data = ingest_result.get("data", {})
    chunks = data.get("chunks_created", 0)
    total_v = data.get("total_vectors_in_store", 0)
    check("Ingest API returned success", ok)
    check("Chunks created (> 0)", chunks > 0, f"{chunks} chunks created in {elapsed}s")
    check("Vectors stored in FAISS", total_v > 0, f"{total_v} vectors in store")
    if ok and chunks > 0:
        stage_times = data.get("stage_times_sec", {})
        print(f"\n      📊 Stage Timings:")
        for stage, t in stage_times.items():
            print(f"         • {stage}: {t}s")
except Exception as e:
    check("Ingest API", False, str(e))

# ─── Stage 4: Chunker Quality Check ─────────────────────────
print("\n✂️  STAGE 4: Chunker Quality")
print("-" * 40)
try:
    from app.services.chunker import get_chunker
    from app.services.pdfparser import PDFParserService

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
        tf.write(pdf_bytes)
        tmp_path = tf.name

    doc = PDFParserService.extract_fast_text(tmp_path)
    os.unlink(tmp_path)

    chunker = get_chunker("layout_aware")
    chunks = chunker.chunk(doc)
    avg_len = sum(len(c.text) for c in chunks) / max(len(chunks), 1)
    max_len = max((len(c.text) for c in chunks), default=0)

    check("Chunks produced", len(chunks) > 0, f"{len(chunks)} chunks")
    check("Avg chunk size < 600 chars", avg_len < 600, f"avg={avg_len:.0f} chars, max={max_len} chars")
    check("No giant chunks (< 800 chars max)", max_len < 800, f"max chunk = {max_len} chars")

    print(f"\n      📦 Chunk Preview (first 3):")
    for i, c in enumerate(chunks[:3]):
        preview = c.text[:80].replace("\n", " ")
        print(f"         #{i+1} [{c.chunk_type}] p{c.page_number} ({len(c.text)}c): {preview}...")
except Exception as e:
    check("Chunker quality check", False, str(e))

# ─── Stage 5: Query Retrieval ─────────────────────────────────
print("\n🔍 STAGE 5: Query & Retrieval Accuracy")
print("-" * 40)
test_queries = [
    ("what is NexaShield?", "nexashield"),
    ("deep learning pipeline", "cnn"),
    ("grad-cam explainable ai", "grad-cam"),
]

for query, expected_keyword in test_queries:
    try:
        result = post_form(
            f"{BASE}/api/v1/query",
            {"query": query, "embedding_model": "minilm", "top_k": "3", "filter_chunk_type": "text"}
        )
        ok = result.get("success") is True
        results_list = result.get("data", {}).get("results", [])
        hits = [r for r in results_list if expected_keyword.lower() in (r.get("chunk_text", "")).lower()]
        top_score = results_list[0].get("match_percentage", "0%") if results_list else "N/A"
        check(
            f'Query: "{query[:35]}..."',
            ok and len(hits) > 0,
            f"top match={top_score}, keyword '{expected_keyword}' found={len(hits)}/{len(results_list)}"
        )
    except Exception as e:
        check(f'Query: "{query[:35]}"', False, str(e))

# ─── Stage 6: Match % Sanity ─────────────────────────────────
print("\n📊 STAGE 6: Match Percentage Sanity")
print("-" * 40)
try:
    result = post_form(
        f"{BASE}/api/v1/query",
        {"query": "NexaShield deepfake detection forensic", "embedding_model": "minilm", "top_k": "1"}
    )
    r = result.get("data", {}).get("results", [{}])[0]
    score_str = r.get("match_percentage", "0%")
    score = int(score_str.replace("%", ""))
    check("Top result match > 30%", score > 30, f"Got {score_str} for highly relevant query")
    check("match_percentage field present", "match_percentage" in r, f"fields: {list(r.keys())[:6]}")
except Exception as e:
    check("Match percentage check", False, str(e))

# ─── Summary ──────────────────────────────────────────────────
print("\n" + "="*60)
total = len(results)
passed = sum(1 for _, ok in results if ok)
failed = total - passed
status = "🟢 ALL CLEAR" if failed == 0 else f"🔴 {failed} FAILURE(S) DETECTED"
print(f"  {status}  —  {passed}/{total} checks passed")
print("="*60 + "\n")

if failed > 0:
    print("Failed checks:")
    for name, ok in results:
        if not ok:
            print(f"  ❌ {name}")
