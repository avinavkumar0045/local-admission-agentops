# AgentOps and Explainability for a Local Admission Information Agent

## 📖 Overview
This project builds a robust, privacy-safe, local-first AI agent to answer university admission queries. Unlike standard RAG (Retrieval-Augmented Generation) applications, the core engineering focus is on **Instrumentation-by-Design**. 

By building an embedded observability layer (AgentOps) from day one, we conduct a controlled experiment to measure the exact value of telemetry in diagnosing failures, tracking execution traces, and providing explainable AI responses.

## 🏗 Architecture
The system employs a strict Dual-Path Architecture:

### 1. The Functional AI Pipeline
- **Stack:** Local Qwen LLM, FAISS (Vector DB) / Neo4j (Graph DB), FastAPI, Streamlit
- **Flow:** Student Query ➔ Retrieval (Semantic + Relational) ➔ LLM Generation ➔ Explainable Final Response.

### 2. The AgentOps Pipeline (Telemetry)
- **Stack:** OpenTelemetry, MySQL (Relational DB), Grafana
- **Flow:** Trace Emission ➔ Structured Storage (MySQL) ➔ Monitoring & Alerting (Grafana).

> **Key Architectural Decision: Instrumentation-by-Design (Option 2)**
> The AgentOps telemetry is baked INTO the agent from Day 1. This prevents architectural rework, avoids technical debt, and ensures accurate data collection for the final controlled comparison (AgentOps ON vs OFF).

## 🚀 Getting Started (Phase 0)

### Hardware Requirements
- Apple Silicon Mac (M-series, e.g., M2 Air) with at least 8-16 GB unified memory.

### Setup Instructions
1. **Install Ollama:** Download from [ollama.com](https://ollama.com/)
2. **Pull the Model:** Open your terminal and run:
   ```bash
   ollama run qwen2.5-coder:latest
   ```
3. **Install Python Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## 📂 Project Structure
- `/data`: Contains source admission documents, FAISS indexes, and database files.
- `/src/agent`: Core logic for the RAG agent (retrieval, generation, explainability).
- `/src/agentops`: Telemetry and instrumentation interfaces, MySQL schema.
- `/ui`: Streamlit frontend application.
- `tracker.txt`: Living document tracking project updates and facts.

## 🧪 Experimentation & Metrics
The final phase of this project involves injecting intentional failures (e.g., database timeouts, context corruption) to measure:
1. Trace Completeness
2. Alert Precision/Recall
3. Diagnosis Time
4. Telemetry Overhead (Cost of observability)
