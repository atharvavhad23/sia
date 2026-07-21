# SIA PDF Extraction Microservice API

## Overview
This microservice provides an enterprise-ready endpoint for extracting textual data, metadata, and tabular structures from PDF documents. It is designed to be highly fault-tolerant and fast, making it ideal for ingestion pipelines prior to vector embeddings.

## Base URL
`http://127.0.0.1:8000`

---

## 1. Health Check
Checks if the API is currently online.

- **Endpoint:** `/`
- **Method:** `GET`
- **Responses:**
  - `200 OK`: `{"status": "online", "service": "SIA Backend Utilities"}`

---

## 2. Extract PDF
Extracts data from an uploaded PDF document based on the specified engine and format.

- **Endpoint:** `/api/v1/extract`
- **Method:** `POST`
- **Content-Type:** `multipart/form-data`

### Form Parameters
| Parameter | Type | Required | Default | Description |
| :--- | :--- | :--- | :--- | :--- |
| `file` | file | **Yes** | - | The PDF document to upload. |
| `engine` | string | No | `fast` | The extraction engine to use. Must be `fast`, `structural`, or `hybrid`. |
| `output_format` | string | No | `json` | The output format response. Must be `json` or `markdown`. |

### Engine Options
- **`fast` (PyMuPDF):** Blazing fast text extraction. Good for standard documents without tables.
- **`structural` (pdfplumber):** Preserves visual structure. Slower, but highly accurate.
- **`hybrid` (Camelot + PyMuPDF):** The best of both. Uses computer vision to perfectly extract tables, and PyMuPDF to extract text at high speeds.

### Error Responses
| Status Code | Reason | Example |
| :--- | :--- | :--- |
| `400 Bad Request` | Uploaded file is not a `.pdf` | `{"detail": "Only PDF files are supported."}` |
| `400 Bad Request` | Invalid parameters | `{"detail": "Engine must be 'fast', 'structural', or 'hybrid'."}` |
| `400 Bad Request` | PDF is password-protected | `{"detail": "Password-protected PDF"}` |
| `400 Bad Request` | PDF is corrupted | `{"detail": "Corrupted or unreadable PDF"}` |
| `500 Internal Server Error` | Unexpected backend failure | `{"detail": "Internal Server Error during extraction."}` |

### Examples

**1. Extract using the Hybrid Engine as JSON (curl):**
```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/extract' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'engine=hybrid' \
  -F 'output_format=json' \
  -F 'file=@financial_report.pdf;type=application/pdf'
```

**2. Extract using the Fast Engine as Markdown (Python):**
```python
import requests

url = "http://127.0.0.1:8000/api/v1/extract"
files = {'file': open('contract.pdf', 'rb')}
data = {'engine': 'fast', 'output_format': 'markdown'}

response = requests.post(url, files=files, data=data)
print(response.text)
```
