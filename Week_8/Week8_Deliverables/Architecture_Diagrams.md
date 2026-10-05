# Architecture Diagrams — SIA RAG Microservice

> All diagrams are Mermaid source so they live in version control as text and render natively in GitHub, GitLab, and most markdown previewers.

---

## 1. System / Component Diagram

Shows every service in the deployed stack and how they communicate.

```mermaid
graph TD
    subgraph Client Layer
        Browser["Browser / API Client"]
    end

    subgraph Application Layer
        FastAPI["FastAPI Server\n(uvicorn, 1–N workers)"]
        Middleware["Latency Middleware\n(X-Process-Time header)"]
    end

    subgraph Cache Layer
        Redis["Redis 7\n(query result cache)\nTTL: 3600s"]
    end

    subgraph ML / Processing Layer
        MiniLM["all-MiniLM-L6-v2\n(sentence-transformers)\n384-dim dense embeddings"]
        PyMuPDF["PyMuPDF\n(fast text extraction)"]
        Chunker["LayoutAwareChunker\n(layout-aware splitting)"]
    end

    subgraph Storage Layer
        LanceDB["LanceDB\n(on-disk PyArrow)\ncosine similarity search"]
        Volume[("vector_store/\n(Docker volume)")]
    end

    Browser --> FastAPI
    FastAPI --> Middleware
    FastAPI -->|"1. Cache lookup"| Redis
    FastAPI -->|"2a. Embed query"| MiniLM
    FastAPI -->|"2b. ANN search"| LanceDB
    LanceDB --> Volume
    FastAPI -->|"Ingest path only"| PyMuPDF
    PyMuPDF --> Chunker
    Chunker -->|"embed chunks"| MiniLM
    MiniLM -->|"upsert vectors"| LanceDB
```

---

## 2. Query Request Sequence Diagram

Detailed step-by-step flow for a single `POST /api/v1/query` request.

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant FastAPI
    participant Redis
    participant MiniLM as MiniLM Embedder
    participant LanceDB
    participant QA as Extractive QA

    Client->>FastAPI: POST /api/v1/query {query, top_k, model}
    FastAPI->>FastAPI: Validate & normalize query string
    FastAPI->>Redis: GET sha256(query|model|top_k)
    alt Cache HIT (~5ms)
        Redis-->>FastAPI: Cached JSON result
        FastAPI-->>Client: 200 OK {cache_hit: true, ...}
    else Cache MISS (~200–500ms)
        Redis-->>FastAPI: null
        FastAPI->>MiniLM: embed_query(query_text) → 384-dim vector
        MiniLM-->>FastAPI: query_vector
        FastAPI->>LanceDB: cosine_search(query_vector, top_k×4)
        LanceDB-->>FastAPI: raw_results[]
        FastAPI->>FastAPI: Filter + deduplicate metadata
        FastAPI->>QA: _extract_answer_snippets(query, results)
        QA->>MiniLM: embed(sentences) → sentence vectors
        MiniLM-->>QA: sentence_vectors
        QA->>QA: argmax cosine similarity → best_sentence
        QA-->>FastAPI: results with answer_snippet
        FastAPI->>Redis: SETEX key TTL result_json
        FastAPI-->>Client: 200 OK {cache_hit: false, results: [...]}
    end
```

---

## 3. Document Ingestion Flow

Flow for a `POST /api/v1/ingest` request (CPU-heavy, run in threadpool).

```mermaid
flowchart TD
    A["Client: POST /api/v1/ingest\n(multipart/form-data PDF)"] --> B["Validate: .pdf extension,\nnon-empty, valid PDF header"]
    B --> C["Save to temp_docs/ with UUID filename"]
    C --> D["run_in_threadpool → ingest_document()"]

    subgraph Stage 1: Extract
        D --> E{"engine param"}
        E -->|fast| F["PyMuPDF: extract_fast_text()\n~50ms for typical doc"]
        E -->|structural| G["Camelot: extract_structural_text()\n~800ms, finds tables"]
        E -->|hybrid| H["PyMuPDF + Camelot combined"]
    end

    subgraph Stage 2: Chunk
        F & G & H --> I["LayoutAwareChunker\n(respects headers/paragraphs)"]
        I --> J["List of Chunk objects\nwith page_number, section_title"]
    end

    subgraph Stage 3: Embed
        J --> K["all-MiniLM-L6-v2\nembed(texts, batch_size=32)\n→ np.ndarray shape (N, 384)"]
    end

    subgraph Stage 4: Metadata
        K --> L["Attach ChunkMetadata:\ndocument_id, chunk_id, source_filename,\nchunking_strategy, page, token_count..."]
    end

    subgraph Stage 5: Store
        L --> M["LanceDBVectorStore.upsert()\n→ appends to PyArrow table\nPersisted to disk immediately"]
    end

    M --> N["Invalidate Redis cache\n(purge all sia:query:* keys)"]
    N --> O["Return ingest summary:\ndocument_id, chunks_created,\nstage_times_sec"]
    O --> P["Delete temp file"]
```
