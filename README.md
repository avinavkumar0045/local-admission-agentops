# AgentOps: Instrumentation-by-Design for Local RAG Agents

<p align="center">
  <img src="Agent%20page%20.png" width="49%" alt="Admission Agent Streamlit UI" />
  <img src="Graffana%20Dashboard.png" width="49%" alt="Grafana Tempo Trace Explorer" />
</p>

## 1. Abstract
As Large Language Models (LLMs) transition from conversational wrappers into autonomous agents, the complexity of debugging and evaluating their workflows has scaled exponentially. Traditional text-based logging is insufficient for diagnosing failures in multi-step architectures. This project demonstrates **Instrumentation-by-Design**—embedding native observability (AgentOps) directly into an agent's architecture from inception, ensuring operational transparency, rapid root-cause analysis, and automated failure alerting.

## 2. System Architecture

To ensure isolated and accurate performance measurements, the system employs a strict **Dual-Path Architecture**:

### 2.1 The Functional AI Pipeline
*   **LLM Engine:** Local Qwen 2.5 Coder (via Ollama)
*   **Vector Database:** FAISS (Facebook AI Similarity Search)
*   **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
*   **Knowledge Base:** A massive, chunked index (991 semantic chunks) ingested from high-density PDFs (e.g., JEE Advanced Brochures) and tabular Excel data (e.g., AISHE Reports).
*   **Orchestration:** FastAPI backend serving a custom Streamlit UI.

### 2.2 The AgentOps Trace Pipeline
*   **Instrumentation Layer:** OpenTelemetry SDK (Python)
*   **Collector Node:** OpenTelemetry Collector (Docker)
*   **Storage & Visualization:** Grafana Tempo (Traces) and MySQL (Metrics)
*   **Trace Contract:** Enforces a rigid 11-step cascading waterfall trace for every query (e.g., `admission.query`, `faiss.search`, `llm.generation`). Span attributes capture internal AI logic, including `source_files`, `total_chunks_in_db`, and exact error tracebacks.

## 3. Observability & Alerting Features

*   **Deep-Dive Trace Explorer:** High-level metrics seamlessly link directly to Tempo's 11-step trace waterfalls. Developers can click a `trace_id` to visually isolate pipeline bottlenecks down to the microsecond.
*   **Failure Injection Taxonomy:** The architecture successfully isolates and categorizes distinct failure modes (e.g., `LLM_INFERENCE_ERROR`, `RETRIEVAL_DB_OUTAGE`) bypassing generic HTTP 500 errors.
*   **Automated Alerting:** Grafana constantly monitors backend spans. If a critical failure condition is breached, a Webhook instantly routes a high-priority alert to the engineering team.

## 4. Installation & Quickstart

### Prerequisites
*   Apple Silicon Mac (M-series) with at least 8-16 GB unified memory.
*   Docker & Docker Compose.
*   Python 3.10+

### Setup Instructions

**1. Initialize the Observability Backend (Docker)**
```bash
docker-compose up -d
```
*This boots the OpenTelemetry Collector on port 4317 and Grafana Tempo.*

**2. Initialize the AI Engine (Ollama)**
```bash
ollama serve
# In a separate terminal, pull the model if required:
ollama run qwen2.5-coder:latest
```

**3. Launch the AgentOps API (FastAPI)**
```bash
python -m uvicorn src.agent.api:app --port 8000
```

**4. Launch the Frontend Interface (Streamlit)**
```bash
python -m streamlit run ui/app.py --server.port 8501
```

## 5. Experimental Results
In a controlled A/B experiment simulating catastrophic database and LLM parsing failures, the un-instrumented baseline ("AgentOps OFF") required manual parsing of unstructured terminal logs, yielding a high Mean Time to Resolution (MTTR). 

When AgentOps was enabled, Grafana instantly fired a webhook alert, and the Trace Explorer highlighted the exact failing span (`llm.generation`) in red. Observability overhead added zero measurable latency to the end-user, proving that native OpenTelemetry tracing is a mandatory, low-cost requirement for production-grade AI engineering.
