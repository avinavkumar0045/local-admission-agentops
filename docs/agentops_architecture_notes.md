# AgentOps High-Level Architecture — Verification Notes

**File:** `docs/agentops_architecture_notes.md`  
**Diagram source:** `docs/agentops_high_level_architecture.mmd`  
**Inspection date:** October 2026  
**Verification method:** Direct source-code and configuration file inspection (Phase 1)

---

## 1. Source Files Inspected

| File | Purpose Verified |
|---|---|
| `src/agent/api.py` | FastAPI endpoint, span orchestration, MySQL emit |
| `src/agent/retriever.py` | FAISS search, embedding call, OTel spans, source_files attribute |
| `src/agent/generator.py` | Ollama HTTP call, prompt assembly, error span |
| `src/agent/prompts.py` | SYSTEM_INSTRUCTIONS, build_prompt(), FALLBACK_RESPONSE |
| `src/agent/ingest.py` | PDF/CSV/Excel/MD parsing, chunking, FAISS index write |
| `src/agentops/telemetry.py` | OTel SDK setup, TracerProvider, OTLPSpanExporter, MySQL connector |
| `src/agentops/schema.sql` | MySQL schema: sessions, traces, spans tables |
| `src/config.py` | AGENTOPS_ENABLED flag, DB credentials, Ollama URL, model name |
| `ui/app.py` | Streamlit chat UI, explainability expander, httpx POST |
| `ui/styles.css` | CSS styling (no architectural relevance) |
| `otel-collector-config.yaml` | OTLP receiver on 0.0.0.0:4317, exporter to tempo:4317 |
| `tempo-config.yaml` | HTTP port 3200, OTLP receiver, local block storage /tmp/tempo |
| `docker-compose.yml` | Two services: tempo, otel-collector; bridge network agentops-network |
| `alert_receiver.py` | FastAPI on port 5050, POST /alert handler, console print |
| `data/raw/` | 9 PDFs, 5 CSVs, 3 Excel files, 2 Markdown files confirmed present |
| `data/vector_store/` | faiss.index + metadata.json confirmed present |

---

## 2. Architectural Layers Explained

### Layer A — User & Presentation Layer
**Technology:** Streamlit (`ui/app.py`) · Port 8501  
**Responsibility:** Renders the chat interface, submits queries to the FastAPI backend via `httpx.post`, and displays the AI answer alongside a collapsible "View Sources (Explainability)" expander panel.  
**Explainability:** The expander renders the source filename, relevance distance, and chunk text for every retrieved document, exposing the RAG grounding to the student user.

### Layer B — Application & Orchestration Layer
**Technology:** FastAPI (`src/agent/api.py`) · Uvicorn · Port 8000  
**Responsibility:** Single entry point (`POST /query`). Generates a UUID `trace_id`, opens the OTel root span (`admission.query`), orchestrates the retrieval and generation pipeline, writes a summary record to MySQL, and returns `{trace_id, answer, context}` to the UI.

### Layer C — AI & Retrieval Layer
**Technology:** FAISS, sentence-transformers, Ollama  
**Components verified in code:**
- `FAISSRetriever` — encodes the query, searches the FAISS Flat L2 index, applies a distance threshold of 1.5, and sets `source_files` on the OTel span.
- `LocalQwenGenerator` — calls `build_prompt()`, posts to Ollama's `/api/generate` endpoint with a 180s timeout.
- `prompts.py` — defines `SYSTEM_INSTRUCTIONS`, `build_prompt()`, and `FALLBACK_RESPONSE` as a single editable rules file.
- Ollama runtime serves `qwen2.5-coder:latest` at `localhost:11434`. No data egress — fully local.

### Layer D — Knowledge Ingestion (Offline Path)
**Technology:** pypdf, pandas, openpyxl (`src/agent/ingest.py`)  
**Responsibility:** Parses raw documents (PDFs, CSVs, Excel, Markdown), chunks text, generates embeddings, and writes vectors + metadata to `data/vector_store/`. **This is a run-once offline process, not executed per query.**  
**Current state:** 991 chunks indexed across 19 source files confirmed in `data/raw/`.

### Layer E — AgentOps Observability Layer
**Technology:** OpenTelemetry Python SDK, OTel Collector (Docker), Grafana Tempo (Docker), MySQL (Homebrew)

**Verified connections (from code + config):**
1. `telemetry.py` creates a `TracerProvider` with `OTLPSpanExporter` pointing to `http://localhost:4317` (gRPC, insecure).
2. `otel-collector-config.yaml` binds a gRPC receiver on `0.0.0.0:4317` and exports to `tempo:4317` (Docker internal network).
3. Tempo stores traces as local blocks at `/tmp/tempo/blocks` (ephemeral — cleared on Docker restart).
4. `telemetry.py` also opens a `mysql.connector` connection and inserts custom span records into `agentops_db.spans` (sessions → traces → spans schema).
5. **MySQL stores custom span records (span_type, duration_ms, status, metadata JSON). It does NOT store full OTel traces.** Full OTel traces go exclusively to Tempo.

**OTel Span Contract (11 spans per query, verified in code):**  
`admission.query` → `query.validation` → `retrieval` → `embedding_generation` → `faiss.search` → `context.selection` → `llm.generation` → `prompt.construction` → `grounding.validation` → `explanation` → `response`

### Layer F — Alerting & Failure Management
**Technology:** Grafana alert engine, Webhook Contact Point, FastAPI alert receiver  
**Verified:**
- Grafana Alert Rule "AgentOps Failure Detected" evaluates `SELECT COUNT(*) FROM spans WHERE status = 'error' OR status = 'failure'` against MySQL every 60 seconds.
- On `FIRING`, Grafana posts `{alerts: [{status, annotations}]}` to `http://localhost:5050/alert`.
- `alert_receiver.py` is a standalone FastAPI app on port 5050 that parses the payload and prints to console.

---

## 3. Principal Data and Telemetry Paths

### Online Query Path (solid arrows in diagram)
```
Student → Streamlit → FastAPI → FAISSRetriever → [Embedder → FAISS → Metadata]
       → FastAPI → Generator → [Prompts → Ollama]
       → FastAPI → Streamlit → Student (answer + sources)
```

### Offline Ingestion Path (dashed arrows in diagram)
```
Raw Documents → Ingest Pipeline → [Embed + Index] → FAISS Index + Metadata JSON
```
*Run manually once. Not triggered by user queries.*

### OTel Telemetry Path (double arrows in diagram)
```
FastAPI (OTel SDK) → OTLP/gRPC localhost:4317 → OTel Collector (Docker)
                   → OTLP/gRPC tempo:4317     → Grafana Tempo (Docker)
FastAPI (MySQL tracker) → SQL INSERT           → MySQL agentops_db.spans
```

### Monitoring & Alerting Path
```
Grafana → SQL SELECT  → MySQL (metrics dashboard)
Grafana → Trace API   → Tempo (trace explorer + data links)
Grafana → Alert Rule  → Webhook HTTP POST → Alert Receiver (port 5050)
```

---

## 4. Implementation Status of Every Component

| Component | Status | Evidence |
|---|---|---|
| Streamlit Chat UI | ✅ Implemented | `ui/app.py` — full chat + expander |
| Explainability Panel (source attribution) | ✅ Implemented | UI expander + `source_files` OTel attribute |
| FastAPI `/query` endpoint | ✅ Implemented | `api.py` with Pydantic models |
| FAISSRetriever | ✅ Implemented | `retriever.py` — full k-NN + threshold |
| SentenceTransformer embedding | ✅ Implemented | `all-MiniLM-L6-v2` in retriever |
| FAISS index (991 vectors) | ✅ Implemented | `data/vector_store/faiss.index` exists |
| Metadata store | ✅ Implemented | `data/vector_store/metadata.json` exists |
| Prompt builder / rules file | ✅ Implemented | `prompts.py` with SYSTEM_INSTRUCTIONS |
| LocalQwenGenerator | ✅ Implemented | `generator.py` — full Ollama HTTP call |
| Ollama / Qwen inference | ✅ Implemented | Confirmed at `localhost:11434` |
| Document ingestion (PDF/CSV/Excel/MD) | ✅ Implemented | `ingest.py` — pypdf, pandas, openpyxl |
| OTel SDK instrumentation | ✅ Implemented | `telemetry.py` — TracerProvider + OTLP exporter |
| 11-span trace contract | ✅ Implemented | Verified across `api.py`, `retriever.py`, `generator.py` |
| OTel Collector (Docker) | ✅ Implemented | `otel-collector-config.yaml` + `docker-compose.yml` |
| Grafana Tempo (Docker) | ✅ Implemented | `tempo-config.yaml` + `docker-compose.yml` |
| MySQL agentops_db | ✅ Implemented | `schema.sql` + `telemetry.py` connector |
| Grafana dashboard | ✅ Implemented | Provisioned via `build_dashboard.py` API script |
| Grafana Alert Rule | ✅ Implemented | Configured in Grafana UI + confirmed firing |
| Webhook Contact Point | ✅ Implemented | `alert_receiver.py` + Grafana config |
| Alert Receiver (port 5050) | ✅ Implemented | `alert_receiver.py` |
| AGENTOPS_ENABLED feature flag | ✅ Implemented | `src/config.py` |
| Failure taxonomy (`failure_class`) | ✅ Implemented | OTel attribute set on error spans |
| Automated RAGAS evaluation | ❌ Not implemented | Planned Phase 11 |
| LLM-as-judge quality scoring | ❌ Not implemented | Planned Phase 11 |
| External API integrations | ❌ Not present | Not in codebase |
| Message queues / brokers | ❌ Not present | Not in codebase |
| Authentication / rate limiting | ❌ Not present | Not in codebase |

---

## 5. Implementation Discrepancies Found

| Item | Documentation Claim | Verified Reality |
|---|---|---|
| MySQL stores OTel traces | Implied by some docs | **False.** MySQL stores custom summary records only (`span_type`, `duration_ms`, `status`, `metadata` JSON). Full OTel traces go to Tempo only. |
| Tempo receives data directly from app | Implied by some descriptions | **False.** The app sends OTLP to the **OTel Collector** first (port 4317 on host), which then forwards to Tempo on the Docker internal network (`tempo:4317`). |
| Tempo storage is persistent | Implied | **Partially true.** Storage is local (`/tmp/tempo/blocks`) and is **ephemeral** — cleared on Docker restart. Only newly generated traces are queryable. |
| All 11 spans are always emitted | Stated in docs | **Mostly true.** If context is empty, `prompt.construction` returns `FALLBACK_RESPONSE` early, and downstream spans (`grounding.validation`, `explanation`, `response`) may still be emitted by `api.py` regardless. |

---

## 6. Diagram Legend

| Arrow Style | Meaning |
|---|---|
| `→` Solid arrow | Synchronous application data flow (online query path) |
| `-.->` Dashed arrow | Offline / asynchronous path (ingestion — not per-query) |
| `==>` Bold arrow | Telemetry export and observability signals |

| Node Color | Layer |
|---|---|
| Dark teal / green | Application services and AI pipeline |
| Dark purple | Storage (FAISS, MySQL, Tempo) |
| Dark orange-brown | Raw document files |
| Dark navy | OTel / observability components |
| Dark red | Alerting components |
| Deep purple | External runtime (Ollama) |
