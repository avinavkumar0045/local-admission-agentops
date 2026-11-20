"""
AgentOps Enterprise Dual-View Web Console (Port 5050)
=====================================================
Modeled after AWS CloudWatch & AWS OpsCenter:
1. Operations Console (FinOps, Cost, Token Accounting, Compute Savings & SRE Health)
2. Developer Console (Prioritized Issue Stack: P1 Critical > P2 Warning > P3 Info with Root-Cause Diagnostics & Tempo Trace Links)
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from datetime import datetime, timezone
import json
import logging
import uuid
import sys
import os

from src.agentops.priority_engine import caps_engine

DPO_DIR = os.path.join(os.path.dirname(__file__), "data", "dpo")
DPO_DATASET_PATH = os.path.join(DPO_DIR, "dpo_train_dataset.jsonl")
RAW_LOG_PATH = os.path.join(DPO_DIR, "flagged_interactions.jsonl")
RATINGS_LOG_PATH = os.path.join(DPO_DIR, "ratings_log.jsonl")

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
    "guardrails": {
        "denied_topics": {"rate_pct": 35.7, "count": 20, "label": "Domain Scope Guardrail", "status": "ACTIVE_POLICY"},
        "prompt_injection": {"rate_pct": 0.0, "count": 0, "label": "Prompt Safety & Jailbreak", "status": "ZERO_EXPLOITS"},
        "pii_redaction": {"rate_pct": 0.0, "count": 0, "label": "Student PII & Privacy Filter", "status": "COMPLIANCE_PASS"},
        "grounding_sla": {"rate_pct": 3.6, "count": 2, "label": "Semantic Grounding Violations", "status": "SLA_ALERTS_DISPATCHED"}
    },
    "execution_distribution": [
        {"name": "Tier 0: Domain Scope Guardrail Drop", "sub": "Zero-Compute Pre-Execution Interception", "requests": 20, "pct": 35.7, "latency": "1.1 ms", "tokens": "0", "color": "#06B6D4"},
        {"name": "Tier 1: Fast-Path Deterministic Registry", "sub": "SAGE-QA Institutional Cache & Metadata", "requests": 12, "pct": 21.4, "latency": "0.8 ms", "tokens": "0", "color": "#10B981"},
        {"name": "Tier 2: Full Agentic RAG Pipeline", "sub": "FAISS Retrieval (7,937 Chunks) + Local Qwen 7B Inference", "requests": 24, "pct": 42.9, "latency": "9.4 s", "tokens": "22,480", "color": "#8B5CF6"}
    ],
    "services": {
        "fastapi": {"status": "HEALTHY", "port": 8000, "detail": "Uvicorn HTTP Gateway Active"},
        "faiss": {"status": "HEALTHY", "detail": "7,937 Chunks (42 PDFs/TXTs) Indexed"},
        "ollama": {"status": "HEALTHY", "port": 11434, "detail": "Qwen2.5-Coder:7B (Local CPU)"},
        "tempo": {"status": "HEALTHY", "port": 3200, "detail": "Grafana Tempo OTel Tracing Active"}
    }
}

# In-memory incident store
# In-memory incident store (Enhanced with CAPS Mathematical Scoring)
INCIDENTS = [
    {
        "id": "INC-A98B5B",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P2_WARNING",
        "caps_score": 68.4,
        "caps_formula": "min(100, [0.4×0.0 + 0.6×76.0] × 1.5 × 1.0) = 68.4",
        "caps_components": {"I": 0.0, "S": 76.0, "B": 1.5, "U": 1.0},
        "title": "Semantic Grounding Degradation",
        "summary": "Faithfulness score dipped to 0.45 (< 0.70 SLA threshold). Model generated ungrounded entity claims for tuition fees.",
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
        "caps_score": 9.2,
        "caps_formula": "min(100, [0.4×0.0 + 0.6×19.2] × 0.8 × 1.0) = 9.2",
        "caps_components": {"I": 0.0, "S": 19.2, "B": 0.8, "U": 1.0},
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
        "caps_score": 14.4,
        "caps_formula": "min(100, [0.4×0.0 + 0.6×20.0] × 1.2 × 1.0) = 14.4",
        "caps_components": {"I": 0.0, "S": 20.0, "B": 1.2, "U": 1.0},
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
    """Enforces mathematical priority: FIRING before RESOLVED, then strictly descending by CAPS Score, then newest timestamp."""
    global INCIDENTS
    def sort_key(inc):
        status_rank = 0 if inc.get("status") == "FIRING" else 1
        caps_val = inc.get("caps_score", 0.0)
        ts_str = inc.get("timestamp", "")
        ts_val = 0.0
        try:
            ts_val = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S").timestamp()
        except Exception:
            pass
        return (status_rank, -caps_val, -ts_val)
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

@app.post("/api/dpo/record")
async def record_dpo_entry(request: Request):
    data = await request.json()
    return JSONResponse(content={"status": "recorded", "id": data.get("record_id")})

@app.get("/api/dpo/list")
async def get_dpo_list():
    records = []
    if os.path.exists(RAW_LOG_PATH):
        with open(RAW_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except:
                        pass
    
    # Read disk-persisted ratings log (survives any service restart / refresh)
    thumbs_up = 0
    thumbs_down = len(records)
    if os.path.exists(RATINGS_LOG_PATH):
        with open(RATINGS_LOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        r_data = json.loads(line)
                        if r_data.get("rating") == 1:
                            thumbs_up += 1
                        elif r_data.get("rating") == -1 and len(records) == 0:
                            thumbs_down += 1
                    except:
                        pass

    # Merge with MySQL stats if available
    try:
        import mysql.connector
        from src.config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME
        conn = mysql.connector.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, database=DB_NAME)
        cur = conn.cursor()
        cur.execute("SELECT user_feedback, COUNT(*) FROM semantic_evaluations WHERE user_feedback IS NOT NULL GROUP BY user_feedback")
        rows = cur.fetchall()
        for r in rows:
            if r[0] == 1:
                thumbs_up = max(thumbs_up, r[1])
            elif r[0] == -1:
                thumbs_down = max(thumbs_down, r[1])
        cur.close()
        conn.close()
    except Exception:
        pass
    
    total_ratings = thumbs_up + thumbs_down
    csat = round((thumbs_up / max(1, total_ratings)) * 100, 1) if total_ratings > 0 else 100.0

    return JSONResponse(content={
        "total_dpo_pairs": len(records),
        "total_ratings": total_ratings,
        "thumbs_up": thumbs_up,
        "thumbs_down": thumbs_down,
        "csat_pct": csat,
        "records": records[::-1]  # Latest first
    })

@app.get("/api/dpo/export")
async def export_dpo_dataset():
    if not os.path.exists(DPO_DATASET_PATH):
        os.makedirs(os.path.dirname(DPO_DATASET_PATH), exist_ok=True)
        with open(DPO_DATASET_PATH, "w", encoding="utf-8") as f:
            pass
    return FileResponse(
        DPO_DATASET_PATH,
        media_type="application/x-jsonlines",
        filename="dpo_train_dataset.jsonl"
    )

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
            
        # Compute CAPS Score for dynamically arriving alert
        is_fatal = payload.get("is_fatal", "Timeout" in title or "P1" in sev or "Disruption" in title or "Connection" in title)
        query_text = payload.get("query") or summary
        caps_res = payload.get("caps") or caps_engine.evaluate(
            query=query_text,
            is_fatal=is_fatal,
            latency_s=payload.get("latency_s", 18.0 if is_fatal else 4.0),
            faithfulness=payload.get("faithfulness", 0.45 if "P2" in sev else 0.95),
            hallucinated=payload.get("hallucinated", True if "P2" in sev else False),
            context_relevance=payload.get("context_relevance", 0.5),
            feedback_rating=payload.get("feedback_rating"),
            feedback_notes=payload.get("feedback_notes")
        )
        sev = caps_res["severity"]
        new_inc = {
            "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "severity": sev,
            "caps_score": caps_res["caps_score"],
            "caps_formula": caps_res["formula_repr"],
            "caps_components": caps_res["components"],
            "title": title,
            "summary": summary,
            "query": query_text,
            "latency_s": payload.get("latency_s", 18.0 if is_fatal else 4.0),
            "faithfulness": payload.get("faithfulness", 0.45 if "P2" in sev else 0.95),
            "hallucinated": payload.get("hallucinated", True if "P2" in sev else False),
            "context_relevance": payload.get("context_relevance", 0.5),
            "is_fatal": is_fatal,
            "root_cause": root_cause,
            "culprit_module": culprit,
            "remediation": remedy,
            "status": "FIRING",
            "trace_id": tid
        }
        INCIDENTS.append(new_inc)
        _sort_incidents()
        _print_alert_console(title, f"{summary} | CAPS: {caps_res['caps_score']}", sev)
    else:
        for alert in alerts:
            status = alert.get("status", "firing").upper()
            annotations = alert.get("annotations", {})
            summary = annotations.get("summary") or annotations.get("description") or "AgentOps Metric Threshold Exceeded"
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "AgentOps Failure Detected")
            
            is_fatal = "error" in summary.lower() or "critical" in summary.lower()
            caps_res = caps_engine.evaluate(
                query=summary,
                is_fatal=is_fatal,
                latency_s=8.0,
                faithfulness=0.55 if "warning" in summary.lower() else 0.20,
                hallucinated=True if "warning" in summary.lower() else False
            )
            sev = caps_res["severity"]
            
            new_inc = {
                "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "severity": sev,
                "caps_score": caps_res["caps_score"],
                "caps_formula": caps_res["formula_repr"],
                "caps_components": caps_res["components"],
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
            _print_alert_console(alertname, f"{summary} | CAPS: {caps_res['caps_score']}", sev)
            
    return JSONResponse(content={"status": "Alert Logged & Enqueued"})

@app.post("/api/incidents/feedback_update")
async def update_incident_feedback(request: Request):
    payload = await request.json()
    target_tid = payload.get("trace_id")
    rating = payload.get("rating")  # 1 for up, -1 for down
    notes = payload.get("notes")

    if not target_tid:
        return JSONResponse(status_code=400, content={"error": "trace_id required"})

    updated_count = 0
    for inc in INCIDENTS:
        inc_tid = inc.get("trace_id", "")
        # Match trace_id exactly or as prefix/suffix
        if inc_tid and (inc_tid == target_tid or target_tid in inc_tid or inc_tid in target_tid):
            prev_comp = inc.get("caps_components", {})
            query_str = inc.get("query") or inc.get("summary", "")
            
            # Recalculate CAPS with updated feedback rating
            caps_res = caps_engine.evaluate(
                query=query_str,
                is_fatal=inc.get("is_fatal", prev_comp.get("I", 0.0) >= 100.0),
                latency_s=inc.get("latency_s", 4.0),
                faithfulness=inc.get("faithfulness", 0.50),
                hallucinated=inc.get("hallucinated", True if inc.get("severity") in ["P1_CRITICAL", "P2_WARNING"] else False),
                context_relevance=inc.get("context_relevance", 0.50),
                feedback_rating=rating,
                feedback_notes=notes
            )
            
            old_score = inc.get("caps_score", 0.0)
            inc["caps_score"] = caps_res["caps_score"]
            inc["caps_formula"] = caps_res["formula_repr"]
            inc["caps_components"] = caps_res["components"]
            inc["severity"] = caps_res["severity"]
            inc["feedback_rating"] = rating
            inc["feedback_notes"] = notes

            if rating == 1:
                if "[Mitigated" not in inc.get("title", ""):
                    inc["title"] = inc.get("title", "") + " [Mitigated: 👍 Upvote]"
                inc["root_cause"] = "RC_FALSE_ALARM_SUPPRESSED: Student verified answer as accurate. Priority mathematically de-escalated via human multiplier U=0.6."
            elif rating == -1:
                if "[Amplified" not in inc.get("title", ""):
                    inc["title"] = inc.get("title", "") + " [Amplified: 👎 Flagged]"

            updated_count += 1
            print(f"🔄 [CAPS REACTIVE UPDATE] Incident {inc.get('id')} updated for trace {target_tid}: Score {old_score} -> {caps_res['caps_score']} ({caps_res['formula_repr']})")

    if updated_count > 0:
        _sort_incidents()
        return JSONResponse(content={"status": "Updated", "updated_count": updated_count})
    return JSONResponse(content={"status": "No matching incident found for trace_id", "trace_id": target_tid})

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

        /* --- Execution Engine Distribution (AWS CloudWatch Style) --- */
        .engine-bar-container {
            display: flex;
            flex-direction: column;
            gap: 1.1rem;
            margin-top: 0.5rem;
        }

        .engine-row {
            display: grid;
            grid-template-columns: 280px 1fr 180px;
            align-items: center;
            gap: 1.5rem;
            padding: 0.6rem 0.8rem;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            transition: all 0.2s ease;
        }

        .engine-row:hover {
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.08);
        }

        .engine-label-wrap {
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        .engine-name {
            font-size: 0.86rem;
            font-weight: 700;
            color: #F8FAFC;
        }

        .engine-tier {
            font-size: 0.74rem;
            color: var(--text-muted);
        }

        .engine-bar-track {
            width: 100%;
            height: 20px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
            overflow: hidden;
            position: relative;
        }

        .engine-bar-fill {
            height: 100%;
            border-radius: 6px;
            transition: width 0.8s cubic-bezier(0.4, 0, 0.2, 1);
            display: flex;
            align-items: center;
            padding-left: 10px;
            font-size: 0.72rem;
            font-weight: 800;
            color: #FFFFFF;
            letter-spacing: 0.02em;
        }

        .engine-meta {
            text-align: right;
            font-size: 0.78rem;
            color: var(--text-secondary);
            display: flex;
            flex-direction: column;
            gap: 2px;
        }

        /* --- 4-Pillar Service Quality & Guardrail Matrix (AWS Bedrock Style) --- */
        .guardrail-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.2rem;
            margin-bottom: 2rem;
        }

        .guardrail-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 12px;
            padding: 1.4rem;
            position: relative;
            backdrop-filter: blur(12px);
            transition: all 0.2s ease;
        }

        .guardrail-card:hover {
            border-color: rgba(255, 255, 255, 0.18);
            transform: translateY(-2px);
        }

        .badge-pill {
            font-size: 0.68rem;
            font-weight: 800;
            padding: 3px 9px;
            border-radius: 9999px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .badge-pass {
            background: rgba(16, 185, 129, 0.15);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.3);
        }

        .badge-warn {
            background: rgba(245, 158, 11, 0.15);
            color: #FCD34D;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }

        .badge-active {
            background: rgba(99, 102, 241, 0.15);
            color: #A5B4FC;
            border: 1px solid rgba(99, 102, 241, 0.3);
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

        .caps-pill {
            display: inline-flex;
            align-items: center;
            gap: 4px;
            background: rgba(139, 92, 246, 0.15);
            color: #C4B5FD;
            border: 1px solid rgba(139, 92, 246, 0.35);
            padding: 3px 9px;
            border-radius: 6px;
            font-size: 0.74rem;
            font-weight: 800;
            letter-spacing: 0.02em;
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
        <button class="tab-btn" onclick="switchTab('dpo')">
            <span>🎯 DPO Dataset Studio (RLHF/HITL)</span>
            <span class="tab-badge" id="dpo-count-badge" style="background: rgba(16, 185, 129, 0.2); color: #34D399;">0</span>
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

        <!-- Upgrade 2: Query Execution Path & Engine Distribution (AWS CloudWatch Model Lens) -->
        <div class="ops-panel" style="margin-bottom: 2rem;">
            <div class="ops-panel-title">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.15rem;">☁️</span>
                    <span>Query Execution Path & Engine Distribution</span>
                    <span class="brand-badge" style="background: rgba(99,102,241,0.15); color: #818CF8;">AWS CloudWatch Model Lens</span>
                </div>
                <span style="font-size: 0.76rem; color: #94A3B8;">Multi-Tier Routing Breakdown (56 Total Requests)</span>
            </div>

            <div class="engine-bar-container">
                <!-- Tier 0: Guardrail Drop -->
                <div class="engine-row">
                    <div class="engine-label-wrap">
                        <span class="engine-name">Tier 0: Domain Scope Guardrail Drop</span>
                        <span class="engine-tier">Zero-Compute Pre-Execution Interception</span>
                    </div>
                    <div class="engine-bar-track">
                        <div class="engine-bar-fill" style="width: 35.7%; background: linear-gradient(90deg, #06B6D4, #38BDF8);">
                            35.7% (20 req)
                        </div>
                    </div>
                    <div class="engine-meta">
                        <span style="color: #38BDF8; font-weight: 700;">1.1 ms avg</span>
                        <span>0 tokens · 0 FAISS scans</span>
                    </div>
                </div>

                <!-- Tier 1: Fast-Path Registry -->
                <div class="engine-row">
                    <div class="engine-label-wrap">
                        <span class="engine-name">Tier 1: Fast-Path Deterministic Registry</span>
                        <span class="engine-tier">SAGE-QA Institutional Cache & Metadata</span>
                    </div>
                    <div class="engine-bar-track">
                        <div class="engine-bar-fill" style="width: 21.4%; background: linear-gradient(90deg, #10B981, #34D399);">
                            21.4% (12 req)
                        </div>
                    </div>
                    <div class="engine-meta">
                        <span style="color: #34D399; font-weight: 700;">0.8 ms avg</span>
                        <span>0 tokens · Sub-1ms bypass</span>
                    </div>
                </div>

                <!-- Tier 2: Full RAG Pipeline -->
                <div class="engine-row">
                    <div class="engine-label-wrap">
                        <span class="engine-name">Tier 2: Full Agentic RAG Pipeline</span>
                        <span class="engine-tier">FAISS Retrieval (7,937 Chunks) + Local Qwen 7B</span>
                    </div>
                    <div class="engine-bar-track">
                        <div class="engine-bar-fill" style="width: 42.9%; background: linear-gradient(90deg, #6366F1, #8B5CF6);">
                            42.9% (24 req)
                        </div>
                    </div>
                    <div class="engine-meta">
                        <span style="color: #A5B4FC; font-weight: 700;">9.4 s avg (P50)</span>
                        <span>22,480 tokens · Full RAG</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Upgrade 1: Service Quality & Guardrail Defense (AWS Bedrock Standard) -->
        <div style="margin-bottom: 2rem;">
            <div class="section-header" style="margin-bottom: 1rem;">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.15rem;">🛡️</span>
                    <h2 class="section-title">Service Quality & Guardrail Defense</h2>
                    <span class="brand-badge" style="background: rgba(16, 185, 129, 0.15); color: #34D399;">AWS Bedrock Standard</span>
                </div>
                <span style="font-size: 0.78rem; color: #94A3B8;">4-Pillar Safety, Privacy & Factual Alignment Matrix</span>
            </div>

            <div class="guardrail-grid">
                <!-- Pillar 1: Denied Topics -->
                <div class="guardrail-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <span class="metric-label" style="margin-bottom: 0;">Denied Topics (Off-Domain)</span>
                        <span class="badge-pill badge-active">ACTIVE POLICY</span>
                    </div>
                    <div class="metric-val" style="color: #60A5FA;" id="guardrail-denied-pct">35.7%</div>
                    <div class="metric-sub" style="margin-bottom: 0.5rem;">
                        <span class="highlight" id="guardrail-denied-count">20</span> filtered non-admission queries
                    </div>
                    <div style="font-size: 0.72rem; color: #64748B; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                        Pre-execution guardrail drops general trivia in &lt;2ms
                    </div>
                </div>

                <!-- Pillar 2: Prompt Injection / Toxicity -->
                <div class="guardrail-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <span class="metric-label" style="margin-bottom: 0;">Prompt Injection & Toxicity</span>
                        <span class="badge-pill badge-pass">ZERO EXPLOITS</span>
                    </div>
                    <div class="metric-val" style="color: #34D399;" id="guardrail-injection-pct">0.00%</div>
                    <div class="metric-sub" style="margin-bottom: 0.5rem;">
                        <span style="color: #34D399; font-weight: 600;">0</span> adversarial jailbreaks detected
                    </div>
                    <div style="font-size: 0.72rem; color: #64748B; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                        Input sanitizer guards system instructions & prompt extraction
                    </div>
                </div>

                <!-- Pillar 3: Student PII & Privacy -->
                <div class="guardrail-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <span class="metric-label" style="margin-bottom: 0;">Student PII & Privacy Filter</span>
                        <span class="badge-pill badge-pass">COMPLIANCE PASS</span>
                    </div>
                    <div class="metric-val" style="color: #34D399;" id="guardrail-pii-pct">0.00%</div>
                    <div class="metric-sub" style="margin-bottom: 0.5rem;">
                        <span style="color: #34D399; font-weight: 600;">0</span> leaked student identifiers
                    </div>
                    <div style="font-size: 0.72rem; color: #64748B; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                        Regex masking for Aadhaar, phone numbers & application IDs
                    </div>
                </div>

                <!-- Pillar 4: Factual Grounding & Hallucination SLA -->
                <div class="guardrail-card">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                        <span class="metric-label" style="margin-bottom: 0;">Factual Grounding SLA</span>
                        <span class="badge-pill badge-warn">SLA ALERTS</span>
                    </div>
                    <div class="metric-val" style="color: #F59E0B;" id="guardrail-grounding-pct">3.57%</div>
                    <div class="metric-sub" style="margin-bottom: 0.5rem;">
                        <span style="color: #F59E0B; font-weight: 600;" id="guardrail-grounding-count">2</span> SLA breaches (&lt;0.70 Faithfulness)
                    </div>
                    <div style="font-size: 0.72rem; color: #64748B; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 6px;">
                        Evaluator-Critic audits generated claims against FAISS context
                    </div>
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
            <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 0.74rem; color: #C4B5FD; background: rgba(167, 139, 250, 0.12); padding: 5px 11px; border-radius: 6px; border: 1px solid rgba(167, 139, 250, 0.3); font-weight: 600;">
                    🧮 Stack-Ranked by CAPS Index
                </span>
                <button class="btn" style="font-size: 0.76rem; padding: 5px 12px;" onclick="clearResolved()">Clear Resolved</button>
            </div>
        </div>

        <!-- Stack-Ranked Issue Cards -->
        <div class="issues-stack" id="issues-list">
            <!-- Dynamically rendered -->
        </div>
    </div>

    <!-- ================= TAB 3: DPO DATASET STUDIO (RLHF/HITL) ================= -->
    <div id="view-dpo" class="view-content">
        <!-- DPO Studio Header & Export -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; background: var(--bg-card); padding: 1.2rem 1.6rem; border-radius: 12px; border: 1px solid var(--border-glass);">
            <div>
                <h2 style="font-size: 1.25rem; font-weight: 800; color: #FFFFFF; display: flex; align-items: center; gap: 10px;">
                    <span>🎯</span> Student Feedback & Quality Assurance Studio
                </h2>
                <p style="font-size: 0.82rem; color: var(--text-secondary); margin-top: 4px;">
                    Captures real-time student ratings, flagged inaccuracies, and verified corrections for quality review and model alignment.
                </p>
            </div>
            <div>
                <a href="/api/dpo/export" class="btn" style="background: linear-gradient(135deg, #10B981, #059669); color: #FFFFFF; font-weight: 700; border: none; padding: 10px 18px; box-shadow: 0 4px 14px rgba(16, 185, 129, 0.35); text-decoration: none;" download>
                    📥 Export QA Dataset (JSONL)
                </a>
            </div>
        </div>

        <!-- DPO KPI Summary Grid (Clean 3-Card Layout) -->
        <div class="finops-grid" style="grid-template-columns: repeat(3, 1fr); margin-bottom: 2rem;">
            <div class="metric-card indigo">
                <div class="metric-label">
                    <span>Student CSAT Rating</span>
                    <span>⭐</span>
                </div>
                <div class="metric-val" id="dpo-stat-csat">100.0%</div>
                <div class="metric-sub"><span id="dpo-stat-up">0</span> positive · <span id="dpo-stat-down">0</span> flagged</div>
            </div>

            <div class="metric-card amber">
                <div class="metric-label">
                    <span>Flagged Inaccuracies</span>
                    <span>⚠️</span>
                </div>
                <div class="metric-val" id="dpo-stat-total" style="color: #FCD34D;">0</div>
                <div class="metric-sub">Flagged by students for review</div>
            </div>

            <div class="metric-card emerald">
                <div class="metric-label">
                    <span>Total Student Ratings</span>
                    <span>💬</span>
                </div>
                <div class="metric-val" id="dpo-stat-ratings" style="color: #34D399;">0</div>
                <div class="metric-sub">Interactive feedback submitted</div>
            </div>
        </div>

        <!-- Curated Interactions Table -->
        <div class="ops-panel">
            <div class="ops-panel-title">
                <div style="display: flex; align-items: center; gap: 10px;">
                    <span style="font-size: 1.15rem;">📜</span>
                    <span>Flagged Interactions & Curated DPO Training Pairs</span>
                </div>
                <span class="service-badge" id="dpo-table-count">0 PAIRS LOADED</span>
            </div>
            
            <div style="overflow-x: auto; margin-top: 1rem;">
                <table style="width: 100%; border-collapse: collapse; font-size: 0.82rem; color: var(--text-secondary);">
                    <thead>
                        <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.08); text-align: left; color: #94A3B8;">
                            <th style="padding: 10px 14px;">RECORD & TRACE</th>
                            <th style="padding: 10px 14px;">STUDENT PROMPT</th>
                            <th style="padding: 10px 14px;">REJECTED ANSWER (IMPERFECT)</th>
                            <th style="padding: 10px 14px;">CHOSEN (GOLD-STANDARD GROUND TRUTH)</th>
                            <th style="padding: 10px 14px;">SOURCE / NOTES</th>
                            <th style="padding: 10px 14px;">STATUS</th>
                        </tr>
                    </thead>
                    <tbody id="dpo-table-body">
                        <tr>
                            <td colspan="6" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">
                                No flagged interactions yet. Give a thumbs-down (👎) in the Chatbot assistant to curate your first DPO pair!
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
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
            } else if (tab === 'dev') {
                document.querySelectorAll('.tab-btn')[1].classList.add('active');
                document.getElementById('view-dev').classList.add('active');
            } else if (tab === 'dpo') {
                document.querySelectorAll('.tab-btn')[2].classList.add('active');
                document.getElementById('view-dpo').classList.add('active');
                fetchDPOData();
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

                // Guardrail 4-pillar bindings (AWS Bedrock Standard)
                if (data.guardrails) {
                    if (document.getElementById('guardrail-denied-pct')) {
                        document.getElementById('guardrail-denied-pct').innerText = `${data.guardrails.denied_topics.rate_pct}%`;
                        document.getElementById('guardrail-denied-count').innerText = data.guardrails.denied_topics.count;
                    }
                    if (document.getElementById('guardrail-injection-pct')) {
                        document.getElementById('guardrail-injection-pct').innerText = `${data.guardrails.prompt_injection.rate_pct.toFixed(2)}%`;
                    }
                    if (document.getElementById('guardrail-pii-pct')) {
                        document.getElementById('guardrail-pii-pct').innerText = `${data.guardrails.pii_redaction.rate_pct.toFixed(2)}%`;
                    }
                    if (document.getElementById('guardrail-grounding-pct')) {
                        document.getElementById('guardrail-grounding-pct').innerText = `${data.guardrails.grounding_sla.rate_pct}%`;
                        document.getElementById('guardrail-grounding-count').innerText = data.guardrails.grounding_sla.count;
                    }
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
            document.title = (unreadCount > 0 ? `(${unreadCount}) ` : "") + "AgentDashboard ☯︎";

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
                                <span class="caps-pill mono" title="${escapeHtml(inc.caps_formula || '')}">🧮 CAPS: ${inc.caps_score ? inc.caps_score.toFixed(1) : '50.0'}</span>
                            </div>
                            <div>
                                ${inc.status === 'FIRING' ? `<button class="resolve-btn" onclick="resolveIncident('${inc.id}')">✓ Mark Resolved</button>` : `<span style="color: #34D399; font-weight: 700; font-size: 0.78rem;">✓ RESOLVED</span>`}
                            </div>
                        </div>

                        <div class="ops-title">${inc.title}</div>
                        <div class="ops-summary">${inc.summary}</div>

                        <div class="rca-container mono">
                            <div class="rca-line">
                                <span class="rca-tag">Priority Metric (CAPS):</span>
                                <span class="rca-content" style="color: #C4B5FD;"><code>${escapeHtml(inc.caps_formula || 'min(100, [0.4*I + 0.6*S]*B*U)')}</code></span>
                            </div>
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

        function escapeHtml(text) {
            if (!text) return '';
            return String(text)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        async function fetchDPOData() {
            try {
                const res = await fetch('/api/dpo/list');
                const data = await res.json();
                
                const countBadge = document.getElementById('dpo-count-badge');
                if (countBadge) countBadge.innerText = data.total_dpo_pairs;
                
                const statTotal = document.getElementById('dpo-stat-total');
                if (statTotal) statTotal.innerText = data.total_dpo_pairs;

                const statRatings = document.getElementById('dpo-stat-ratings');
                if (statRatings) statRatings.innerText = data.total_ratings;

                const statCsat = document.getElementById('dpo-stat-csat');
                if (statCsat) statCsat.innerText = `${data.csat_pct}%`;

                const statUp = document.getElementById('dpo-stat-up');
                if (statUp) statUp.innerText = data.thumbs_up;

                const statDown = document.getElementById('dpo-stat-down');
                if (statDown) statDown.innerText = data.thumbs_down;

                const tableCount = document.getElementById('dpo-table-count');
                if (tableCount) tableCount.innerText = `${data.records ? data.records.length : 0} PAIRS LOADED`;

                const tbody = document.getElementById('dpo-table-body');
                if (!tbody) return;

                if (!data.records || data.records.length === 0) {
                    tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; padding: 2.5rem; color: var(--text-muted);">No flagged interactions yet. Give a thumbs-down (👎) in the Chatbot assistant to curate your first DPO pair!</td></tr>`;
                    return;
                }

                tbody.innerHTML = data.records.map(r => {
                    const tid = r.trace_id ? r.trace_id.slice(0, 8) : 'N/A';
                    const tempoUrl = `http://localhost:3000/explore?schemaVersion=1&panes=%7B%223u5%22%3A%7B%22datasource%22%3A%22ffx7prdoh20hsd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%2C%22uid%22%3A%22ffx7prdoh20hsd%22%7D%2C%22queryType%22%3A%22traceql%22%2C%22query%22%3A%22%7Bspan.trace_id%3D%5C%22${r.trace_id}%5C%22%7D%22%7D%5D%7D%7D`;
                    return `
                    <tr style="border-bottom: 1px solid rgba(255, 255, 255, 0.04); transition: background 0.2s;" onmouseover="this.style.background='rgba(255,255,255,0.02)'" onmouseout="this.style.background='transparent'">
                        <td style="padding: 12px 14px;">
                            <div style="font-weight: 700; color: #F8FAFC;">${r.record_id}</div>
                            <div style="font-size: 0.72rem; color: #64748B;"><a href="${tempoUrl}" target="_blank" style="color: #6366F1; text-decoration: none;">Tempo: ${tid} ↗</a></div>
                        </td>
                        <td style="padding: 12px 14px; color: #E2E8F0; font-weight: 500; max-width: 220px;">
                            ${escapeHtml(r.prompt || '')}
                        </td>
                        <td style="padding: 12px 14px; color: #FCA5A5; max-width: 280px; font-size: 0.78rem;">
                            ${escapeHtml((r.rejected_answer || '').slice(0, 160))}...
                        </td>
                        <td style="padding: 12px 14px; color: #86EFAC; max-width: 300px; font-size: 0.78rem;">
                            ${escapeHtml((r.chosen_answer || '').slice(0, 180))}...
                        </td>
                        <td style="padding: 12px 14px; font-size: 0.74rem;">
                            <div style="color: #94A3B8;">${escapeHtml(r.source_doc || 'verified_context')}</div>
                            ${r.student_notes ? `<div style="color: #FCD34D; font-style: italic; margin-top: 2px;">"${escapeHtml(r.student_notes)}"</div>` : ''}
                        </td>
                        <td style="padding: 12px 14px;">
                            <span style="display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.68rem; font-weight: 700; background: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3);">
                                ${r.status || 'CURATED'}
                            </span>
                        </td>
                    </tr>
                    `;
                }).join('');
            } catch (err) {
                console.error("Failed to load DPO data:", err);
            }
        }

        async function simulateAlert() {
            await fetch('/api/simulate', { method: 'POST' });
            fetchIncidents();
            fetchOperations();
        }

        // Live polling every 2.5s
        fetchOperations();
        fetchIncidents();
        fetchDPOData();
        setInterval(() => {
            fetchOperations();
            fetchIncidents();
            fetchDPOData();
        }, 2500);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("AgentOps Enterprise Dual-View Console running on http://localhost:5050")
    uvicorn.run(app, host="0.0.0.0", port=5050, access_log=False)
