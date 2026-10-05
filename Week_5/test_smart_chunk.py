import re

def smart_chunk_text(text: str, max_chars: int = 500) -> list:
    # 1. Normalize line endings
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    chunks = []
    curr = []
    curr_len = 0
    
    # Common section / item headers: e.g. ALL CAPS, ends with ':', or project titles like "NexaShield: ...", dates "06 Jun, 2025"
    header_pattern = re.compile(r'^(?:[A-Z\s]{3,30}:?|[A-Za-z0-9\s\-]+:|\d{1,2}\s+[A-Za-z]{3},\s+\d{4})')

    for line in lines:
        is_bullet = line.startswith('•') or line.startswith('- ')
        is_header = bool(header_pattern.match(line)) and len(line) < 100
        
        if (is_header or is_bullet) and curr_len > 150:
            chunks.append("\n".join(curr))
            curr = [line]
            curr_len = len(line)
        else:
            if curr_len + len(line) > max_chars and curr:
                chunks.append("\n".join(curr))
                curr = [line]
                curr_len = len(line)
            else:
                curr.append(line)
                curr_len += len(line)
                
    if curr:
        chunks.append("\n".join(curr))
    return chunks

test_resume = \"\"\"ATHARVA RAVIKIRAN AVHAD
B.E. - Information Technology
Ph: +91-7666423899
Email: atharvaavhad2005@gmail.com
EDUCATION
2023 - 2027
Don Bosco Institute of Technology Mumbai
B.E. - Information Technology | CGPA: 8.20 / 10
PROJECTS
11 Jan, 2026 - 22 Jun, 2026
NexaShield: Forensic-Grade Deepfake Detection System for Law Enforcement
Team Size: 1
Key Skills: PyTorch , OpenCV ,Deep Learning Computer Vision ,Convolutional Neural Networks (CNNs)
Built a dual-stream deep learning pipeline using spatial CNNs and DCT spectral analysis to detect AI-generated image and video manipulations.
Integrated Explainable AI (Grad-CAM) to generate visual tampering heatmaps, providing verifiable digital evidence for law enforcement investigations.
Designed for real-world robustness against high WhatsApp/social media compression while securing chain of custody via SHA-256 cryptographic hashing
24 Jan, 2026 - 28 May, 2026
Koyna Biodiversity Analytics of koyna species
Mentor: prof Aruna Khubalkar | Team Size: 4
Key Skills: python , machine learning , xgboost regressor
Built a full-stack wildlife intelligence platform for Koyna Wildlife Sanctuary.\"\"\"

res = smart_chunk_text(test_resume)
print(f"Produced {len(res)} chunks:")
for i, c in enumerate(res):
    print(f"\n--- Chunk {i+1} ({len(c)} chars) ---")
    print(c)
