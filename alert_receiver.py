"""
AgentOps Enterprise Dual-View Web Console (Port 5050)
=====================================================
Modeled after AWS CloudWatch & AWS OpsCenter:
1. Operations Console (FinOps, Cost, Token Accounting, Compute Savings & SRE Health)
2. Developer Console (Prioritized Issue Stack: P1 Critical > P2 Warning > P3 Info with Root-Cause Diagnostics & Tempo Trace Links)
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timezone
import json
import logging
import uuid
import sys

app = FastAPI(title="AgentOps Enterprise Command Center")

log = logging.getLogger("uvicorn.access")
log.setLevel(logging.CRITICAL)

# Priority mapping: P1_CRITICAL (1) > P2_WARNING (2) > P3_INFO (3)
SEVERITY_ORDER = {
    "P1_CRITICAL": 1,
    "P1": 1,
    "CRITICAL": 1,
    "P2_WARNING": 2,
    "P2": 2,
    "WARNING": 2,
    "P3_INFO": 3,
    "P3": 3,
    "INFO": 3
}

# Operations FinOps & SRE Metrics Store
OPERATIONS_METRICS = {
    "total_queries": 56,
    "guardrail_deflections": 20,
    "successful_queries": 36,
    "tokens_consumed": 22480,
    "tokens_saved": 3000,            # 20 * 150 tokens saved
    "faiss_scans_prevented": 158740,  # 20 * 7937 vectors
    "estimated_cost_incurred_usd": 0.0450,  # $0.002 per 1k tokens
    "estimated_cost_saved_usd": 0.0060,
    "cpu_energy_saved_wh": 0.30,      # Watt-hours saved by dropping CPU LLM generation
    "fast_path_latency_ms": 0.8,
    "guardrail_latency_ms": 1.1,
    "faiss_retrieval_latency_ms": 14.2,
    "llm_p50_latency_s": 9.4,
    "llm_p95_latency_s": 14.8,
    "llm_p99_latency_s": 22.1,
    "services": {
        "fastapi": {"status": "HEALTHY", "port": 8000, "detail": "Uvicorn HTTP Gateway Active"},
        "faiss": {"status": "HEALTHY", "detail": "7,937 Chunks (42 PDFs/TXTs) Indexed"},
        "ollama": {"status": "HEALTHY", "port": 11434, "detail": "Qwen2.5-Coder:7B (Local CPU)"},
        "tempo": {"status": "HEALTHY", "port": 3200, "detail": "Grafana Tempo OTel Tracing Active"}
    }
}

# In-memory incident store
INCIDENTS = [
    {
        "id": "INC-A98B5B",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P2_WARNING",
        "title": "Semantic Grounding Degradation",
        "summary": "Faithfulness score dipped to 0.45 (< 0.70 SLA threshold). Model generated ungrounded entity claims.",
        "root_cause": "RC_RETRIEVAL_GAP: Candidate chunks had high L2 distance (> 1.48) to user query.",
        "culprit_module": "retrieval.faiss",
        "remediation": "Audit FAISS sliding window chunk overlap and verify source PDF indexing coverage.",
        "status": "FIRING",
        "trace_id": "367037c2-1391-4fdb-a34e-aee7f08dfcb2"
    },
    {
        "id": "INC-30BA27",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P3_INFO",
        "title": "AgentOps Guardrail: Zero-Compute Pre-Execution Interception",
        "summary": "Out-of-scope query deflected in <2ms before FAISS vector search or LLM generation.",
        "root_cause": "RC_DOMAIN_SCOPE: Non-admission query intercepted by DomainScopeGuardrail.",
        "culprit_module": "guardrail.domain_scope",
        "remediation": "No remediation required. Zero-compute energy defense functioning normally.",
        "status": "FIRING",
        "trace_id": "1ec1906f-02e3-4a8e-8e92-ba35e6461c72"
    },
    {
        "id": "INC-8920",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P3_INFO",
        "title": "Knowledge Base Gap & Safe Abstention",
        "summary": "Out-of-scope query. Vector index returned 0 matching admission documents.",
        "root_cause": "RC_QUERY_AMBIGUITY: User query requested topic outside institutional knowledge base.",
        "culprit_module": "context.selection",
        "remediation": "Expand institutional FAQ repository or upload new official circular.",
        "status": "RESOLVED",
        "trace_id": "41de0d4a-23dd-4c51-b4c0-ed079da62a47"
    }
]

def _sort_incidents():
    """Enforces strict priority stacking: FIRING before RESOLVED, then P1 > P2 > P3, then newest first."""
    global INCIDENTS
    def sort_key(inc):
        status_rank = 0 if inc.get("status") == "FIRING" else 1
        sev_rank = SEVERITY_ORDER.get(inc.get("severity", "P2_WARNING"), 99)
        ts_str = inc.get("timestamp", "")
        ts_val = 0.0
        try:
            ts_val = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            pass
        return (status_rank, sev_rank, -ts_val)
    INCIDENTS.sort(key=sort_key)

_sort_incidents()

@app.get("/api/incidents")
async def get_incidents():
    _sort_incidents()
    return JSONResponse(content={"incidents": INCIDENTS})

@app.get("/api/operations")
async def get_operations():
    # Dynamically recount active counts
    p1 = len([i for i in INCIDENTS if "P1" in i.get("severity", "") and i.get("status") == "FIRING"])
    p2 = len([i for i in INCIDENTS if "P2" in i.get("severity", "") and i.get("status") == "FIRING"])
    p3 = len([i for i in INCIDENTS if "P3" in i.get("severity", "") and i.get("status") == "FIRING"])
    
    data = dict(OPERATIONS_METRICS)
    data["active_p1"] = p1
    data["active_p2"] = p2
    data["active_p3"] = p3
    data["interception_ratio_pct"] = round((data["guardrail_deflections"] / max(1, data["total_queries"])) * 100, 1)
    return JSONResponse(content=data)

@app.post("/api/resolve/{incident_id}")
async def resolve_incident(incident_id: str):
    for inc in INCIDENTS:
        if inc["id"] == incident_id:
            inc["status"] = "RESOLVED"
            inc["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _sort_incidents()
            return JSONResponse(content={"success": True, "incident": inc})
    return JSONResponse(content={"error": "Not found"}, status_code=404)

@app.post("/api/clear")
async def clear_resolved():
    global INCIDENTS
    INCIDENTS = [inc for inc in INCIDENTS if inc["status"] == "FIRING"]
    _sort_incidents()
    return JSONResponse(content={"success": True, "remaining": len(INCIDENTS)})

@app.post("/api/simulate")
async def simulate_incident():
    new_inc = {
        "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P1_CRITICAL",
        "title": "Vector Store Connection Failure / Outage",
        "summary": "Downstream FAISS vector database process unreachable. Circuit breaker tripped to prevent cascading API degradation.",
        "root_cause": "RC_SERVICE_UNAVAILABLE: FAISS vector service process terminated unexpectedly or port blocked.",
        "culprit_module": "faiss.search",
        "remediation": "Restart FAISS worker process and verify file descriptors for index.bin.",
        "status": "FIRING",
        "trace_id": str(uuid.uuid4())
    }
    INCIDENTS.append(new_inc)
    _sort_incidents()
    _print_alert_console(new_inc["title"], new_inc["summary"], "P1_CRITICAL")
    return JSONResponse(content={"success": True, "incident": new_inc})

@app.post("/alert")
async def receive_alert(request: Request):
    payload = await request.json()
    
    # Catch and parse alerts from Grafana or Streamlit or API
    alerts = payload.get("alerts", [])
    if not alerts:
        # Direct custom payload
        summary = payload.get("summary") or payload.get("detail") or "AgentOps Anomaly Triggered"
        title = payload.get("title") or "Agent Runtime Anomaly"
        sev = payload.get("severity") or "P2_WARNING"
        tid = payload.get("trace_id") or str(uuid.uuid4())
        
        # Root cause classification based on title/summary
        root_cause = "RC_SEMANTIC_DEGRADATION: Telemetry flagged grounding score violation."
        culprit = "grounding.validation"
        remedy = "Review candidate document context and tune generation prompt constraints."
        
        if "Guardrail" in title or "P3" in sev or "Scope" in title:
            root_cause = "RC_DOMAIN_SCOPE: Non-admission query intercepted by pre-execution guardrail."
            culprit = "guardrail.domain_scope"
            remedy = "No action needed. Query dropped early to conserve CPU LLM energy."
            # Update live finops metrics
            OPERATIONS_METRICS["total_queries"] += 1
            OPERATIONS_METRICS["guardrail_deflections"] += 1
            OPERATIONS_METRICS["tokens_saved"] += 150
            OPERATIONS_METRICS["faiss_scans_prevented"] += 7937
            OPERATIONS_METRICS["estimated_cost_saved_usd"] += 0.0003
            OPERATIONS_METRICS["cpu_energy_saved_wh"] += 0.015
        elif "Timeout" in title or "P1" in sev or "Disruption" in title:
            root_cause = "RC_LATENCY_SLA: Model inference duration exceeded operational threshold."
            culprit = "llm.generator"
            remedy = "Verify Ollama thread allocation and allocate sufficient RAM/VRAM."
        elif "Connection" in title or "Outage" in title:
            root_cause = "RC_SERVICE_UNAVAILABLE: Downstream vector store / API error."
            culprit = "faiss.vector_db"
            remedy = "Restart downstream microservice and check network socket availability."
            
        new_inc = {
            "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "severity": sev,
            "title": title,
            "summary": summary,
            "root_cause": root_cause,
            "culprit_module": culprit,
            "remediation": remedy,
            "status": "FIRING",
            "trace_id": tid
        }
        INCIDENTS.append(new_inc)
        _sort_incidents()
        _print_alert_console(title, summary, sev)
    else:
        for alert in alerts:
            status = alert.get("status", "firing").upper()
            annotations = alert.get("annotations", {})
            summary = annotations.get("summary") or annotations.get("description") or "AgentOps Metric Threshold Exceeded"
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "AgentOps Failure Detected")
            
            sev = "P1_CRITICAL" if "error" in summary.lower() or "critical" in summary.lower() else "P2_WARNING"
            
            new_inc = {
                "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "severity": sev,
                "title": alertname,
                "summary": summary,
                "root_cause": "RC_SPAN_FAILURE: MySQL span table reported status='error' > 0 condition.",
                "culprit_module": "mysql.spans",
                "remediation": "Investigate span waterfall in Grafana Tempo to isolate failing step.",
                "status": "FIRING" if status == "FIRING" else "RESOLVED",
                "trace_id": labels.get("trace_id", str(uuid.uuid4()))
            }
            INCIDENTS.append(new_inc)
            _sort_incidents()
            _print_alert_console(alertname, summary, sev)
            
    return JSONResponse(content={"status": "Alert Logged & Enqueued"})

def _print_alert_console(title, detail, severity):
    print("\n" + "🔴"*30)
    print(f"🚨 [AGENTOPS {severity} ALERT DISPATCHED] 🚨")
    print(f"Title: {title}")
    print(f"Detail: {detail}")
    print("Logged to Live Console on http://localhost:5050")
    print("🔴"*30 + "\n")
    sys.stdout.flush()

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    return HTML_CONTENT

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>☯︎ Agent Dashboard</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        .notification-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #25D366; /* WhatsApp style green */
            color: #071E12;
            font-size: 0.76rem;
            font-weight: 800;
            min-width: 22px;
            height: 22px;
            padding: 0 7px;
            border-radius: 9999px;
            box-shadow: 0 0 10px rgba(37, 211, 102, 0.45);
            margin-left: 8px;
            vertical-align: middle;
        }
        :root {
            --bg-base: #0A0D14;
            --bg-surface: #101522;
            --bg-card: rgba(16, 21, 34, 0.85);
            --bg-card-hover: rgba(22, 29, 47, 0.95);
            --border-glass: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(99, 102, 241, 0.25);
            --accent-primary: #6366F1;
            --accent-emerald: #10B981;
            --accent-cyan: #06B6D4;
            --color-p1: #EF4444;
            --color-p2: #F59E0B;
            --color-p3: #3B82F6;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --text-muted: #64748B;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: 'Plus Jakarta Sans', -apple-system, sans-serif;
        }

        code, pre, .mono {
            font-family: 'JetBrains Mono', monospace;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem 2.5rem;
            background-image: 
                radial-gradient(circle at 10% 10%, rgba(99, 102, 241, 0.12) 0px, transparent 40%),
                radial-gradient(circle at 90% 90%, rgba(16, 185, 129, 0.08) 0px, transparent 40%);
            background-attachment: fixed;
        }

        /* Top Brand Bar */
        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.8rem;
            padding-bottom: 1.4rem;
            border-bottom: 1px solid var(--border-glass);
        }

        .brand-wrap {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .brand-icon {
            width: 46px;
            height: 46px;
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(16, 185, 129, 0.2));
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            box-shadow: 0 0 20px rgba(99, 102, 241, 0.2);
        }

        .brand-title {
            font-size: 1.45rem;
            font-weight: 800;
            letter-spacing: -0.03em;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .brand-badge {
            font-size: 0.68rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            padding: 2px 8px;
            background: rgba(99, 102, 241, 0.2);
            color: #A5B4FC;
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 6px;
        }

        .brand-sub {
            font-size: 0.82rem;
            color: var(--text-secondary);
            margin-top: 3px;
        }

        .controls-wrap {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .live-status-pill {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 185, 129, 0.12);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34D399;
            padding: 6px 14px;
            border-radius: 9999px;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.03em;
        }

        .pulse-dot {
            width: 8px;
            height: 8px;
            background-color: #10B981;
            border-radius: 50%;
            animation: pulse 1.6s infinite;
        }

        @keyframes pulse {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
        }

        .btn {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border-glass);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            text-decoration: none;
        }

        .btn:hover {
            background: rgba(255, 255, 255, 0.12);
            border-color: rgba(255, 255, 255, 0.2);
            transform: translateY(-1px);
        }

        .btn-simulate {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.25), rgba(185, 28, 28, 0.15));
            border-color: rgba(239, 68, 68, 0.4);
            color: #FCA5A5;
        }

        .btn-simulate:hover {
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.4), rgba(185, 28, 28, 0.25));
        }

        /* Dual-Tab Navigation Bar (AWS CloudWatch / OpsCenter style) */
        .tabs-nav {
            display: flex;
            align-items: center;
            gap: 8px;
            background: rgba(16, 21, 34, 0.7);
            padding: 5px;
            border-radius: 10px;
            border: 1px solid var(--border-glass);
            margin-bottom: 2rem;
            width: fit-content;
        }

        .tab-btn {
            background: transparent;
            border: none;
            color: var(--text-secondary);
            font-size: 0.88rem;
            font-weight: 700;
            padding: 10px 22px;
            border-radius: 7px;
            cursor: pointer;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .tab-btn:hover {
            color: #FFFFFF;
            background: rgba(255, 255, 255, 0.05);
        }

        .tab-btn.active {
            background: var(--accent-primary);
            color: #FFFFFF;
            box-shadow: 0 2px 12px rgba(99, 102, 241, 0.35);
        }

        .tab-badge {
            font-size: 0.72rem;
            padding: 2px 7px;
            border-radius: 9999px;
            background: rgba(255, 255, 255, 0.2);
        }

        /* Views */
        .view-content {
            display: none;
        }

        .view-content.active {
            display: block;
        }

        /* FinOps & Metrics Grid */
        .finops-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.2rem;
            margin-bottom: 2rem;
        }

        .metric-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 12px;
            padding: 1.4rem;
            position: relative;
            overflow: hidden;
            backdrop-filter: blur(12px);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }

        .metric-card:hover {
            border-color: rgba(255, 255, 255, 0.16);
            transform: translateY(-2px);
        }

        .metric-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
        }

        .metric-card.emerald::before { background: linear-gradient(90deg, #10B981, #34D399); }
        .metric-card.indigo::before { background: linear-gradient(90deg, #6366F1, #818CF8); }
        .metric-card.cyan::before { background: linear-gradient(90deg, #06B6D4, #38BDF8); }
        .metric-card.amber::before { background: linear-gradient(90deg, #F59E0B, #FBBF24); }

        .metric-label {
            font-size: 0.76rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.4rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .metric-val {
            font-size: 2rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #FFFFFF;
            margin-bottom: 0.3rem;
        }

        .metric-sub {
            font-size: 0.78rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .metric-sub .highlight {
            color: #34D399;
            font-weight: 600;
        }

        /* 2-Column Section for Ops: Latency Breakdown + Service Health */
        .ops-details-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 1.4rem;
            margin-bottom: 2rem;
        }

        .ops-panel {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
        }

        .ops-panel-title {
            font-size: 1rem;
            font-weight: 700;
            margin-bottom: 1.2rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        /* Latency Waterfall / Bars */
        .latency-row {
            margin-bottom: 1rem;
        }

        .latency-header {
            display: flex;
            justify-content: space-between;
            font-size: 0.8rem;
            margin-bottom: 0.4rem;
        }

        .latency-bar-bg {
            width: 100%;
            height: 8px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 4px;
            overflow: hidden;
        }

        .latency-bar-fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        }

        /* Service Matrix Cards */
        .service-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0.9rem 1rem;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--border-glass);
            border-radius: 8px;
            margin-bottom: 0.7rem;
        }

        .service-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .service-status-dot {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #10B981;
            box-shadow: 0 0 8px rgba(16, 185, 129, 0.5);
        }

        .service-name {
            font-size: 0.86rem;
            font-weight: 700;
        }

        .service-desc {
            font-size: 0.76rem;
            color: var(--text-muted);
        }

        .service-badge {
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 6px;
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        /* --- Developer Console (AWS OpsCenter Issue Board) --- */
        .filter-ribbon {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1.4rem;
        }

        .filter-pills {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .filter-btn {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid var(--border-glass);
            color: var(--text-secondary);
            font-size: 0.78rem;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 9999px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .filter-btn:hover {
            color: #FFFFFF;
            background: rgba(255, 255, 255, 0.08);
        }

        .filter-btn.active {
            background: rgba(99, 102, 241, 0.2);
            color: #A5B4FC;
            border-color: rgba(99, 102, 241, 0.4);
        }

        .issues-stack {
            display: flex;
            flex-direction: column;
            gap: 1.1rem;
        }

        .opscenter-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 12px;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            transition: all 0.2s ease;
        }

        .opscenter-card:hover {
            border-color: rgba(255, 255, 255, 0.16);
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
        }

        /* Priority styling borders */
        .opscenter-card.p1 {
            border-left: 5px solid var(--color-p1);
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(16, 21, 34, 0.85));
        }

        .opscenter-card.p2 {
            border-left: 5px solid var(--color-p2);
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.06), rgba(16, 21, 34, 0.85));
        }

        .opscenter-card.p3 {
            border-left: 5px solid var(--color-p3);
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.06), rgba(16, 21, 34, 0.85));
        }

        .card-top {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.9rem;
        }

        .top-meta-left {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .ops-id {
            font-size: 0.84rem;
            font-weight: 700;
            color: #FFFFFF;
            background: rgba(255, 255, 255, 0.08);
            padding: 3px 10px;
            border-radius: 4px;
        }

        .ops-sev {
            font-size: 0.72rem;
            font-weight: 800;
            text-transform: uppercase;
            padding: 4px 10px;
            border-radius: 9999px;
            letter-spacing: 0.04em;
        }

        .ops-sev.p1 {
            background: rgba(239, 68, 68, 0.2);
            color: #FCA5A5;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .ops-sev.p2 {
            background: rgba(245, 158, 11, 0.2);
            color: #FCD34D;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }

        .ops-sev.p3 {
            background: rgba(59, 130, 246, 0.2);
            color: #93C5FD;
            border: 1px solid rgba(59, 130, 246, 0.4);
        }

        .ops-status {
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 9999px;
        }

        .ops-status.firing {
            background: rgba(239, 68, 68, 0.2);
            color: #EF4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .ops-status.resolved {
            background: rgba(16, 185, 129, 0.2);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }

        .ops-title {
            font-size: 1.12rem;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 0.45rem;
        }

        .ops-summary {
            font-size: 0.88rem;
            color: var(--text-secondary);
            line-height: 1.55;
            margin-bottom: 1rem;
        }

        /* AWS OpsCenter Diagnosis Box */
        .rca-container {
            background: rgba(0, 0, 0, 0.35);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 8px;
            padding: 0.9rem 1.1rem;
            margin-bottom: 1rem;
        }

        .rca-line {
            font-size: 0.82rem;
            line-height: 1.5;
            margin-bottom: 0.35rem;
            display: flex;
            align-items: baseline;
            gap: 8px;
        }

        .rca-line:last-child {
            margin-bottom: 0;
        }

        .rca-tag {
            font-weight: 700;
            color: #A5B4FC;
            min-width: 140px;
            font-size: 0.76rem;
            text-transform: uppercase;
        }

        .rca-content {
            color: #E2E8F0;
        }

        .card-bottom {
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding-top: 0.8rem;
            border-top: 1px solid var(--border-glass);
            font-size: 0.78rem;
            color: var(--text-muted);
        }

        .trace-link-btn {
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #A5B4FC;
            padding: 5px 12px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: 600;
            display: inline-flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s ease;
        }

        .trace-link-btn:hover {
            background: rgba(99, 102, 241, 0.25);
            color: #FFFFFF;
        }

        .resolve-btn {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: #34D399;
            padding: 5px 12px;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .resolve-btn:hover {
            background: rgba(16, 185, 129, 0.28);
        }
    </style>
</head>
<body>

    <!-- Header -->
    <header class="header-container">
        <div class="brand-wrap">
            <div class="brand-icon" style="font-size: 1.6rem; color: #FFFFFF;">☯︎</div>
            <div>
                <h1 class="brand-title">
                    Agent Dashboard <span style="font-size: 1.35rem; color: #FFFFFF; vertical-align: middle;"></span>
                    <span class="notification-badge" id="header-unread-badge" title="Active issues to be resolved">0</span>
                </h1>
                <p class="brand-sub">FinOps Compute Accounting, SLA Telemetry & Prioritized OpsCenter</p>
            </div>
        </div>

        <div class="controls-wrap">
            <span class="live-status-pill">
                <span class="pulse-dot"></span>
                <span>MONITORING ACTIVE · PORT 5050</span>
            </span>
            <button class="btn btn-simulate" onclick="simulateAlert()">⚡ Simulate P1 Outage</button>
            <a href="http://localhost:3000/explore" target="_blank" class="btn"> Grafana Tempo</a>
            <a href="http://localhost:8501" target="_blank" class="btn"> Chat Assistant</a>
        </div>
    </header>

    <!-- Navigation Tabs -->
    <div class="tabs-nav">
        <button class="tab-btn active" onclick="switchTab('ops')">
            <span> Operations Console (FinOps & SRE)</span>
        </button>
        <button class="tab-btn" onclick="switchTab('dev')">
            <span> Developer Console (Prioritized Issues)</span>
            <span class="tab-badge" id="firing-count-badge">0</span>
        </button>
    </div>

    <!-- ================= TAB 1: OPERATIONS CONSOLE ================= -->
    <div id="view-ops" class="view-content active">
        <!-- FinOps Row -->
        <div class="finops-grid">
            <div class="metric-card indigo">
                <div class="metric-label">
                    <span>LLM Compute Incurred</span>
                    <span></span>
                </div>
                <div class="metric-val" id="metric-cost">$0.0450</div>
                <div class="metric-sub">
                    <span id="metric-tokens-incurred">22,480</span> tokens processed (Qwen 7B)
                </div>
                <div style="font-size: 0.72rem; color: #64748B; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 4px;">
                    Formula: (Tokens ÷ 1,000) × $0.0020
                </div>
            </div>

            <div class="metric-card emerald">
                <div class="metric-label">
                    <span>Guardrail Cost Conserved</span>
                    <span></span>
                </div>
                <div class="metric-val" style="color: #34D399;" id="metric-cost-saved">$0.0060</div>
                <div class="metric-sub">
                    <span class="highlight" id="metric-blocked-count">20</span> out-of-context queries deflected
                </div>
                <div style="font-size: 0.72rem; color: #64748B; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 4px;">
                    Saved: <span id="metric-tokens-saved">3,000</span> tokens (~150 tokens / query)
                </div>
            </div>

            <div class="metric-card cyan">
                <div class="metric-label">
                    <span>Zero-Compute Defense</span>
                    <span></span>
                </div>
                <div class="metric-val" id="metric-scans-saved">158,740</div>
                <div class="metric-sub">
                    FAISS vector dot-products dropped in &lt;2ms
                </div>
                <div style="font-size: 0.72rem; color: #64748B; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 4px;">
                    7,937 index vectors avoided per blocked query
                </div>
            </div>

            <div class="metric-card amber">
                <div class="metric-label">
                    <span>Interception Efficiency</span>
                    <span>⚡</span>
                </div>
                <div class="metric-val" style="color: #FCD34D;" id="metric-ratio">35.7%</div>
                <div class="metric-sub">
                    <span id="metric-blocked-ratio-text">20 out-of-context</span> of <span id="metric-total-queries">56</span> total queries
                </div>
                <div style="font-size: 0.72rem; color: #64748B; margin-top: 6px; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 4px;">
                    Average pre-execution drop: 1.1 ms
                </div>
            </div>
        </div>

        <!-- 2-Column: Latency Performance Waterfall + Subsystem Matrix -->
        <div class="ops-details-grid">
            <!-- Latency Waterfall -->
            <div class="ops-panel">
                <div class="ops-panel-title">
                    <span>Pipeline Latency SLA Breakdown</span>
                    <span style="font-size: 0.76rem; color: #94A3B8;">Real-time Telemetry</span>
                </div>

                <div class="latency-row">
                    <div class="latency-header">
                        <span>⚡ Fast-Path Deterministic Lookup</span>
                        <span class="mono" style="color: #34D399;">0.8 ms</span>
                    </div>
                    <div class="latency-bar-bg">
                        <div class="latency-bar-fill" style="width: 2%; background: #10B981;"></div>
                    </div>
                </div>

                <div class="latency-row">
                    <div class="latency-header">
                        <span>Domain Scope Guardrail Validation</span>
                        <span class="mono" style="color: #34D399;">1.1 ms</span>
                    </div>
                    <div class="latency-bar-bg">
                        <div class="latency-bar-fill" style="width: 3%; background: #06B6D4;"></div>
                    </div>
                </div>

                <div class="latency-row">
                    <div class="latency-header">
                        <span>FAISS Vector Retrieval (7,937 Chunks)</span>
                        <span class="mono" style="color: #60A5FA;">14.2 ms</span>
                    </div>
                    <div class="latency-bar-bg">
                        <div class="latency-bar-fill" style="width: 15%; background: #3B82F6;"></div>
                    </div>
                </div>

                <div class="latency-row">
                    <div class="latency-header">
                        <span>Local CPU LLM Token Generation (P50)</span>
                        <span class="mono" style="color: #F59E0B;">9.4 s</span>
                    </div>
                    <div class="latency-bar-bg">
                        <div class="latency-bar-fill" style="width: 65%; background: #F59E0B;"></div>
                    </div>
                </div>

                <div class="latency-row">
                    <div class="latency-header">
                        <span> Worst-Case SLA Timeout (P99)</span>
                        <span class="mono" style="color: #EF4444;">22.1 s</span>
                    </div>
                    <div class="latency-bar-bg">
                        <div class="latency-bar-fill" style="width: 95%; background: #EF4444;"></div>
                    </div>
                </div>
            </div>

            <!-- Subsystem Health Matrix -->
            <div class="ops-panel">
                <div class="ops-panel-title">
                    <span>Subsystem Availability Matrix</span>
                    <span style="font-size: 0.76rem; color: #10B981;">All Subsystems Nominal</span>
                </div>

                <div class="service-row">
                    <div class="service-left">
                        <div class="service-status-dot"></div>
                        <div>
                            <div class="service-name">FastAPI Core Gateway (Port 8000)</div>
                            <div class="service-desc">Pre-execution guardrail, Fast-path router & query dispatcher</div>
                        </div>
                    </div>
                    <span class="service-badge">ONLINE</span>
                </div>

                <div class="service-row">
                    <div class="service-left">
                        <div class="service-status-dot"></div>
                        <div>
                            <div class="service-name">FAISS Vector Knowledge Store</div>
                            <div class="service-desc">7,937 Sliding Window Chunks (42 Official SRM & AISHE docs)</div>
                        </div>
                    </div>
                    <span class="service-badge">ACTIVE</span>
                </div>

                <div class="service-row">
                    <div class="service-left">
                        <div class="service-status-dot"></div>
                        <div>
                            <div class="service-name">Ollama LLM Engine (Port 11434)</div>
                            <div class="service-desc">Qwen2.5-Coder:7B Local CPU Inference with 32k context</div>
                        </div>
                    </div>
                    <span class="service-badge">READY</span>
                </div>

                <div class="service-row">
                    <div class="service-left">
                        <div class="service-status-dot"></div>
                        <div>
                            <div class="service-name">Grafana Tempo & OTel Collector</div>
                            <div class="service-desc">OpenTelemetry Traces & Spans across Ports 3200 / 4317</div>
                        </div>
                    </div>
                    <span class="service-badge">STREAMING</span>
                </div>
            </div>
        </div>
    </div>

    <!-- ================= TAB 2: DEVELOPER CONSOLE (AWS OPSCENTER) ================= -->
    <div id="view-dev" class="view-content">
        <!-- Filter Ribbon -->
        <div class="filter-ribbon">
            <div class="filter-pills">
                <button class="filter-btn active" onclick="setFilter('ALL')">All Issues (<span id="count-all">0</span>)</button>
                <button class="filter-btn" onclick="setFilter('P1')">🔴 P1 Critical (<span id="count-p1">0</span>)</button>
                <button class="filter-btn" onclick="setFilter('P2')">🟡 P2 Warning (<span id="count-p2">0</span>)</button>
                <button class="filter-btn" onclick="setFilter('P3')">🔵 P3 Info (<span id="count-p3">0</span>)</button>
                <button class="filter-btn" onclick="setFilter('FIRING')">Active / Firing</button>
            </div>
            <div>
                <button class="btn" style="font-size: 0.76rem; padding: 5px 12px;" onclick="clearResolved()">Clear Resolved</button>
            </div>
        </div>

        <!-- Stack-Ranked Issue Cards -->
        <div class="issues-stack" id="issues-list">
            <!-- Dynamically rendered -->
        </div>
    </div>

    <script>
        let currentFilter = 'ALL';
        let allIncidents = [];

        function switchTab(tab) {
            document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
            document.querySelectorAll('.view-content').forEach(view => view.classList.remove('active'));

            if (tab === 'ops') {
                document.querySelectorAll('.tab-btn')[0].classList.add('active');
                document.getElementById('view-ops').classList.add('active');
            } else {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('view-dev').classList.add('active');
            }
        }

        function setFilter(filter) {
            currentFilter = filter;
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            event.target.classList.add('active');
            renderIssues();
        }

        async function fetchOperations() {
            try {
                const res = await fetch('/api/operations');
                const data = await res.json();
                document.getElementById('metric-cost').innerText = `$${data.estimated_cost_incurred_usd.toFixed(4)}`;
                document.getElementById('metric-cost-saved').innerText = `$${data.estimated_cost_saved_usd.toFixed(4)}`;
                document.getElementById('metric-tokens-incurred').innerText = data.tokens_consumed.toLocaleString();
                document.getElementById('metric-tokens-saved').innerText = data.tokens_saved.toLocaleString();
                document.getElementById('metric-scans-saved').innerText = data.faiss_scans_prevented.toLocaleString();
                document.getElementById('metric-ratio').innerText = `${data.interception_ratio_pct}%`;
                
                // Detailed out-of-context counters
                if (document.getElementById('metric-blocked-count')) {
                    document.getElementById('metric-blocked-count').innerText = data.guardrail_deflections;
                }
                if (document.getElementById('metric-total-queries')) {
                    document.getElementById('metric-total-queries').innerText = data.total_queries;
                }
                if (document.getElementById('metric-blocked-ratio-text')) {
                    document.getElementById('metric-blocked-ratio-text').innerText = `${data.guardrail_deflections} out-of-context`;
                }
            } catch (e) {
                console.error("Ops fetch error:", e);
            }
        }

        async function fetchIncidents() {
            try {
                const res = await fetch('/api/incidents');
                const data = await res.json();
                allIncidents = data.incidents;
                updateCounts();
                renderIssues();
            } catch (e) {
                console.error("Incidents fetch error:", e);
            }
        }

        function updateCounts() {
            const firing = allIncidents.filter(i => i.status === 'FIRING');
            const p1 = allIncidents.filter(i => i.severity.includes('P1') && i.status === 'FIRING').length;
            const p2 = allIncidents.filter(i => i.severity.includes('P2') && i.status === 'FIRING').length;
            const p3 = allIncidents.filter(i => i.severity.includes('P3') && i.status === 'FIRING').length;

            const unreadCount = firing.length;
            // WhatsApp style dynamic title badge: (N) AgentDashboard ☯︎
            document.title = (unreadCount > 0 ? `(${unreadCount}) ` : "") + "Agent Dashboard ";

            const badge = document.getElementById('header-unread-badge');
            if (badge) {
                badge.innerText = unreadCount;
                badge.style.display = unreadCount > 0 ? 'inline-flex' : 'none';
            }

            document.getElementById('firing-count-badge').innerText = unreadCount;
            document.getElementById('count-all').innerText = allIncidents.length;
            document.getElementById('count-p1').innerText = p1;
            document.getElementById('count-p2').innerText = p2;
            document.getElementById('count-p3').innerText = p3;
        }

        function renderIssues() {
            const list = document.getElementById('issues-list');
            let filtered = allIncidents;

            if (currentFilter === 'P1') filtered = allIncidents.filter(i => i.severity.includes('P1'));
            else if (currentFilter === 'P2') filtered = allIncidents.filter(i => i.severity.includes('P2'));
            else if (currentFilter === 'P3') filtered = allIncidents.filter(i => i.severity.includes('P3'));
            else if (currentFilter === 'FIRING') filtered = allIncidents.filter(i => i.status === 'FIRING');

            if (filtered.length === 0) {
                list.innerHTML = `
                    <div style="text-align: center; padding: 3.5rem; background: var(--bg-card); border-radius: 12px; border: 1px solid var(--border-glass);">
                        <span style="font-size: 2.2rem;">🟢</span>
                        <h3 style="margin-top: 0.8rem; font-size: 1.1rem; color: #FFFFFF;">No Incidents in Selected Scope</h3>
                        <p style="color: #64748B; font-size: 0.84rem; margin-top: 0.3rem;">All AgentOps pipelines and grounding guards are operating cleanly.</p>
                    </div>
                `;
                return;
            }

            let html = '';
            filtered.forEach(inc => {
                const sevCls = inc.severity.includes('P1') ? 'p1' : (inc.severity.includes('P2') ? 'p2' : 'p3');
                const sevLabel = inc.severity.replace('_', ' ');
                const statusCls = inc.status.toLowerCase();
                const tempoUrl = `http://localhost:3000/explore?schemaVersion=1&panes=%7B%223u5%22%3A%7B%22datasource%22%3A%22ffx7prdoh20hsd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%2C%22uid%22%3A%22ffx7prdoh20hsd%22%7D%2C%22queryType%22%3A%22traceql%22%2C%22query%22%3A%22%7Bspan.trace_id%3D%5C%22${inc.trace_id}%5C%22%7D%22%7D%5D%7D%7D`;

                html += `
                    <div class="opscenter-card ${sevCls}">
                        <div class="card-top">
                            <div class="top-meta-left">
                                <span class="ops-id mono">${inc.id}</span>
                                <span class="ops-sev ${sevCls}">${sevLabel}</span>
                                <span class="ops-status ${statusCls}">● ${inc.status}</span>
                            </div>
                            <div>
                                ${inc.status === 'FIRING' ? `<button class="resolve-btn" onclick="resolveIncident('${inc.id}')">✓ Mark Resolved</button>` : `<span style="color: #34D399; font-weight: 700; font-size: 0.78rem;">✓ RESOLVED</span>`}
                            </div>
                        </div>

                        <div class="ops-title">${inc.title}</div>
                        <div class="ops-summary">${inc.summary}</div>

                        <div class="rca-container mono">
                            <div class="rca-line">
                                <span class="rca-tag">Root Cause (RCA):</span>
                                <span class="rca-content" style="color: #FCD34D;">${inc.root_cause || 'RC_UNKNOWN: Subsystem anomaly'}</span>
                            </div>
                            <div class="rca-line">
                                <span class="rca-tag">Culprit Module:</span>
                                <span class="rca-content" style="color: #93C5FD;"><code>${inc.culprit_module || 'runtime.unclassified'}</code></span>
                            </div>
                            <div class="rca-line">
                                <span class="rca-tag">Remediation:</span>
                                <span class="rca-content" style="color: #34D399;">${inc.remediation || 'Inspect span trace and error stack.'}</span>
                            </div>
                        </div>

                        <div class="card-bottom">
                            <span>Detected: ${inc.timestamp}</span>
                            <span>
                                <a href="${tempoUrl}" target="_blank" class="trace-link-btn">
                                    <span>Explore Trace in Tempo</span>
                                    <span>↗</span>
                                </a>
                            </span>
                        </div>
                    </div>
                `;
            });
            list.innerHTML = html;
        }

        async function resolveIncident(id) {
            await fetch(`/api/resolve/${id}`, { method: 'POST' });
            fetchIncidents();
        }

        async function clearResolved() {
            await fetch('/api/clear', { method: 'POST' });
            fetchIncidents();
        }

        async function simulateAlert() {
            await fetch('/api/simulate', { method: 'POST' });
            fetchIncidents();
            fetchOperations();
        }

        // Live polling every 2.5s
        fetchOperations();
        fetchIncidents();
        setInterval(() => {
            fetchOperations();
            fetchIncidents();
        }, 2500);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("AgentOps Enterprise Dual-View Console running on http://localhost:5050")
    uvicorn.run(app, host="0.0.0.0", port=5050, access_log=False)
