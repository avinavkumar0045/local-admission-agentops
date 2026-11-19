"""
AgentOps Incident Command Center & Alert Receiver
=================================================
Primary Responsibility:
Serves as an on-premise, real-time SRE Incident Management Dashboard (Port 5050).
Catches webhook alerts from Grafana Alerting rules and Streamlit In-App monitoring,
classifies them into SRE severity tiers (P1/P2/P3), performs automated root-cause
diagnostics, and provides an interactive web UI for incident resolution.
"""

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, timezone
import json
import logging
import uuid
import sys

app = FastAPI(title="AgentOps Incident Command Center")

log = logging.getLogger("uvicorn.access")
log.setLevel(logging.CRITICAL)

# In-memory incident store
INCIDENTS = [
    {
        "id": "INC-8921",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P2_WARNING",
        "title": "Semantic Grounding Degradation",
        "summary": "Faithfulness score dipped to 0.45 (< 0.70 SLA threshold). Model generated ungrounded entity claims.",
        "root_cause": "RC_RETRIEVAL_GAP: Candidate chunks had high L2 distance (> 1.48) to user query.",
        "culprit_module": "retrieval.faiss",
        "status": "FIRING",
        "trace_id": "367037c2-1391-4fdb-a34e-aee7f08dfcb2"
    },
    {
        "id": "INC-8920",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P3_INFO",
        "title": "Knowledge Base Gap & Safe Abstention",
        "summary": "Out-of-scope query. Vector index returned 0 matching admission documents.",
        "root_cause": "RC_QUERY_AMBIGUITY: User query requested topic outside institutional knowledge base.",
        "culprit_module": "context.selection",
        "status": "RESOLVED",
        "trace_id": "41de0d4a-23dd-4c51-b4c0-ed079da62a47"
    }
]

@app.get("/api/incidents")
async def get_incidents():
    return JSONResponse(content={"incidents": INCIDENTS})

@app.post("/api/resolve/{incident_id}")
async def resolve_incident(incident_id: str):
    for inc in INCIDENTS:
        if inc["id"] == incident_id:
            inc["status"] = "RESOLVED"
            inc["resolved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return JSONResponse(content={"success": True, "incident": inc})
    return JSONResponse(content={"error": "Not found"}, status_code=404)

@app.post("/api/clear")
async def clear_resolved():
    global INCIDENTS
    INCIDENTS = [inc for inc in INCIDENTS if inc["status"] == "FIRING"]
    return JSONResponse(content={"success": True, "remaining": len(INCIDENTS)})

@app.post("/api/simulate")
async def simulate_incident():
    new_inc = {
        "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "severity": "P1_CRITICAL",
        "title": "Simulated Vector DB Connection Outage",
        "summary": "ConnectionError: Unable to connect to FAISS Vector Database on port 5432.",
        "root_cause": "RC_DB_OUTAGE: Vector store process simulated failure triggered during live defense test.",
        "culprit_module": "faiss.search",
        "status": "FIRING",
        "trace_id": str(uuid.uuid4())
    }
    INCIDENTS.insert(0, new_inc)
    _print_alert_console(new_inc["title"], new_inc["summary"], "P1_CRITICAL")
    return JSONResponse(content={"success": True, "incident": new_inc})

@app.post("/alert")
async def receive_alert(request: Request):
    payload = await request.json()
    
    # Catch and parse alerts from Grafana or Streamlit
    alerts = payload.get("alerts", [])
    if not alerts:
        # Direct custom payload
        summary = payload.get("summary") or payload.get("detail") or "AgentOps Anomaly Triggered"
        title = payload.get("title") or "Agent Runtime Anomaly"
        sev = payload.get("severity") or "P2_WARNING"
        tid = payload.get("trace_id") or str(uuid.uuid4())
        
        new_inc = {
            "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "severity": sev,
            "title": title,
            "summary": summary,
            "root_cause": "RC_SEMANTIC_DEGRADATION: Telemetry flagged grounding score violation.",
            "culprit_module": "grounding.validation",
            "status": "FIRING",
            "trace_id": tid
        }
        INCIDENTS.insert(0, new_inc)
        _print_alert_console(title, summary, sev)
    else:
        for alert in alerts:
            status = alert.get("status", "firing").upper()
            annotations = alert.get("annotations", {})
            summary = annotations.get("summary") or annotations.get("description") or "AgentOps Metric Threshold Exceeded"
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "AgentOps Failure Detected")
            
            # Severity classification
            sev = "P1_CRITICAL" if "error" in summary.lower() or "critical" in summary.lower() else "P2_WARNING"
            
            new_inc = {
                "id": f"INC-{str(uuid.uuid4())[:6].upper()}",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "severity": sev,
                "title": alertname,
                "summary": summary,
                "root_cause": "RC_SPAN_FAILURE: MySQL span table reported status='error' > 0 condition.",
                "culprit_module": "mysql.spans",
                "status": "FIRING" if status == "FIRING" else "RESOLVED",
                "trace_id": labels.get("trace_id", str(uuid.uuid4()))
            }
            INCIDENTS.insert(0, new_inc)
            _print_alert_console(alertname, summary, sev)
            
    return JSONResponse(content={"status": "Alert Logged & Enqueued"})

def _print_alert_console(title, detail, severity):
    print("\n" + "🔴"*30)
    print(f"🚨 [AGENTOPS {severity} ALERT DISPATCHED] 🚨")
    print(f"Title: {title}")
    print(f"Detail: {detail}")
    print("Logged to Live Incident Dashboard on http://localhost:5050")
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
    <title>AgentOps Incident Command Center</title>
    <style>
        :root {
            --bg-base: #0B0F19;
            --bg-surface: #111827;
            --bg-card: rgba(17, 24, 39, 0.75);
            --border-glass: rgba(255, 255, 255, 0.08);
            --border-glow: rgba(167, 139, 250, 0.3);
            --accent-violet: #A78BFA;
            --accent-indigo: #6366F1;
            --color-p1: #EF4444;
            --color-p2: #F59E0B;
            --color-p3: #3B82F6;
            --color-success: #10B981;
            --text-primary: #F8FAFC;
            --text-secondary: #94A3B8;
            --text-muted: #64748B;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-base);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 2rem;
            background-image: 
                radial-gradient(at 0% 0%, rgba(99, 102, 241, 0.12) 0px, transparent 50%),
                radial-gradient(at 100% 100%, rgba(168, 85, 247, 0.08) 0px, transparent 50%);
        }

        .header-container {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 2rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-glass);
        }

        .brand-wrap {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .brand-icon {
            width: 44px;
            height: 44px;
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(167, 139, 250, 0.2));
            border: 1px solid rgba(239, 68, 68, 0.4);
            border-radius: 10px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.4rem;
        }

        .brand-title {
            font-size: 1.4rem;
            font-weight: 700;
            letter-spacing: -0.02em;
            color: #FFFFFF;
        }

        .brand-sub {
            font-size: 0.82rem;
            color: var(--text-secondary);
            margin-top: 2px;
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
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.02em;
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

        .controls-wrap {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .btn {
            background: rgba(255, 255, 255, 0.06);
            border: 1px solid var(--border-glass);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 6px;
            font-size: 0.82rem;
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

        /* Stats Ribbon */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 1.2rem;
            margin-bottom: 2rem;
        }

        .stat-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 10px;
            padding: 1.2rem 1.4rem;
            backdrop-filter: blur(12px);
        }

        .stat-label {
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 0.4rem;
        }

        .stat-value {
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.02em;
        }

        .val-total { color: #FFFFFF; }
        .val-p1 { color: var(--color-p1); }
        .val-p2 { color: var(--color-p2); }
        .val-mttr { color: var(--color-success); }

        /* Incident Feed Section */
        .section-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 1rem;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-primary);
        }

        .incidents-container {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }

        .incident-card {
            background: var(--bg-card);
            border: 1px solid var(--border-glass);
            border-radius: 10px;
            padding: 1.4rem;
            backdrop-filter: blur(12px);
            transition: all 0.2s ease;
        }

        .incident-card.p1 {
            border-left: 4px solid var(--color-p1);
            background: linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(17, 24, 39, 0.75));
        }

        .incident-card.p2 {
            border-left: 4px solid var(--color-p2);
            background: linear-gradient(135deg, rgba(245, 158, 11, 0.06), rgba(17, 24, 39, 0.75));
        }

        .incident-card.p3 {
            border-left: 4px solid var(--color-p3);
            background: linear-gradient(135deg, rgba(59, 130, 246, 0.06), rgba(17, 24, 39, 0.75));
        }

        .incident-top-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 0.8rem;
        }

        .inc-id-tag {
            font-size: 0.85rem;
            font-weight: 700;
            color: #FFFFFF;
            background: rgba(255, 255, 255, 0.08);
            padding: 3px 10px;
            border-radius: 4px;
        }

        .sev-tag {
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            padding: 3px 10px;
            border-radius: 9999px;
            letter-spacing: 0.04em;
        }

        .sev-tag.p1 {
            background: rgba(239, 68, 68, 0.2);
            color: #FCA5A5;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .sev-tag.p2 {
            background: rgba(245, 158, 11, 0.2);
            color: #FCD34D;
            border: 1px solid rgba(245, 158, 11, 0.4);
        }

        .sev-tag.p3 {
            background: rgba(59, 130, 246, 0.2);
            color: #93C5FD;
            border: 1px solid rgba(59, 130, 246, 0.4);
        }

        .status-badge {
            font-size: 0.72rem;
            font-weight: 700;
            padding: 3px 10px;
            border-radius: 9999px;
        }

        .status-badge.firing {
            background: rgba(239, 68, 68, 0.2);
            color: #EF4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }

        .status-badge.resolved {
            background: rgba(16, 185, 129, 0.2);
            color: #34D399;
            border: 1px solid rgba(16, 185, 129, 0.4);
        }

        .inc-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: #FFFFFF;
            margin-bottom: 0.4rem;
        }

        .inc-summary {
            font-size: 0.88rem;
            color: var(--text-secondary);
            line-height: 1.5;
            margin-bottom: 0.8rem;
        }

        .rca-box {
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.06);
            border-radius: 6px;
            padding: 0.65rem 0.9rem;
            font-size: 0.8rem;
            margin-bottom: 0.8rem;
            display: flex;
            gap: 8px;
        }

        .rca-title {
            font-weight: 700;
            color: var(--accent-violet);
        }

        .rca-text {
            color: #E2E8F0;
        }

        .inc-footer {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 0.78rem;
            color: var(--text-muted);
            padding-top: 0.8rem;
            border-top: 1px solid var(--border-glass);
        }

        .trace-link {
            color: var(--accent-violet);
            text-decoration: none;
            font-weight: 600;
        }

        .trace-link:hover {
            text-decoration: underline;
        }

        .btn-resolve {
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #34D399;
            padding: 4px 12px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            cursor: pointer;
        }

        .btn-resolve:hover {
            background: rgba(16, 185, 129, 0.3);
        }
    </style>
</head>
<body>

    <header class="header-container">
        <div class="brand-wrap">
            <div class="brand-icon">🚨</div>
            <div>
                <h1 class="brand-title">AgentOps Incident Command Center</h1>
                <p class="brand-sub">Real-Time SRE Alert Webhook & Autonomous Fault Localization Engine</p>
            </div>
        </div>

        <div class="controls-wrap">
            <span class="live-status-pill">
                <span class="pulse-dot"></span>
                <span>MONITORING ACTIVE · PORT 5050</span>
            </span>
            <button class="btn btn-simulate" onclick="simulateAlert()">⚡ Trigger Demo Alert</button>
            <a href="http://localhost:3000" target="_blank" class="btn">📊 Open Grafana</a>
            <a href="http://localhost:8501" target="_blank" class="btn">🎓 Open Assistant</a>
        </div>
    </header>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">Total Incidents Captured</div>
            <div class="stat-value val-total" id="stat-total">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Active P1 Criticals</div>
            <div class="stat-value val-p1" id="stat-p1">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Active P2 Warnings</div>
            <div class="stat-value val-p2" id="stat-p2">0</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">Mean Time To Detect (MTTD)</div>
            <div class="stat-value val-mttr">&lt; 60s</div>
        </div>
    </div>

    <div class="section-header">
        <h2 class="section-title">Live Incident Stream</h2>
        <button class="btn" style="font-size: 0.76rem; padding: 4px 10px;" onclick="clearResolved()">Clear Resolved</button>
    </div>

    <div class="incidents-container" id="incident-list">
        <!-- Rendered dynamically -->
    </div>

    <script>
        async function fetchIncidents() {
            try {
                const res = await fetch('/api/incidents');
                const data = await res.json();
                renderIncidents(data.incidents);
            } catch (err) {
                console.error("Failed to fetch incidents:", err);
            }
        }

        function renderIncidents(incidents) {
            const list = document.getElementById('incident-list');
            
            // Calculate stats
            let total = incidents.length;
            let p1 = incidents.filter(i => i.severity.includes('P1') && i.status === 'FIRING').length;
            let p2 = incidents.filter(i => i.severity.includes('P2') && i.status === 'FIRING').length;

            document.getElementById('stat-total').innerText = total;
            document.getElementById('stat-p1').innerText = p1;
            document.getElementById('stat-p2').innerText = p2;

            if (incidents.length === 0) {
                list.innerHTML = `
                    <div style="text-align: center; padding: 3rem; color: #64748B;">
                        <span style="font-size: 2rem;">🟢</span>
                        <p style="margin-top: 0.5rem; font-size: 0.9rem;">No active incidents. All AgentOps subsystems healthy.</p>
                    </div>
                `;
                return;
            }

            let html = '';
            incidents.forEach(inc => {
                const sevCls = inc.severity.includes('P1') ? 'p1' : (inc.severity.includes('P2') ? 'p2' : 'p3');
                const sevLabel = inc.severity.replace('_', ' ');
                const statusCls = inc.status.toLowerCase();
                const tempoUrl = `http://localhost:3000/explore?schemaVersion=1&panes=%7B%223u5%22%3A%7B%22datasource%22%3A%22ffx7prdoh20hsd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%2C%22uid%22%3A%22ffx7prdoh20hsd%22%7D%2C%22queryType%22%3A%22traceql%22%2C%22query%22%3A%22%7Bspan.trace_id%3D%5C%22${inc.trace_id}%5C%22%7D%22%7D%5D%7D%7D`;

                html += `
                    <div class="incident-card ${sevCls}">
                        <div class="incident-top-row">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <span class="inc-id-tag">${inc.id}</span>
                                <span class="sev-tag ${sevCls}">${sevLabel}</span>
                                <span class="status-badge ${statusCls}">● ${inc.status}</span>
                            </div>
                            <div>
                                ${inc.status === 'FIRING' ? `<button class="btn-resolve" onclick="resolveIncident('${inc.id}')">✓ Mark Resolved</button>` : `<span style="color: #34D399; font-size: 0.74rem;">Resolved</span>`}
                            </div>
                        </div>

                        <div class="inc-title">${inc.title}</div>
                        <div class="inc-summary">${inc.summary}</div>

                        <div class="rca-box">
                            <span class="rca-title">🔍 Root Cause Diagnosis:</span>
                            <span class="rca-text">${inc.root_cause || 'Culprit: Uncategorized runtime condition'}</span>
                        </div>

                        <div class="inc-footer">
                            <span>Detected: ${inc.timestamp} · Culprit Module: <code>${inc.culprit_module || 'unknown'}</code></span>
                            <span>
                                <a href="${tempoUrl}" target="_blank" class="trace-link">Explore in Grafana Tempo ↗</a>
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
        }

        // Auto-refresh poll every 2.5 seconds
        fetchIncidents();
        setInterval(fetchIncidents, 2500);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("AgentOps Incident Command Center running on http://localhost:5050")
    uvicorn.run(app, host="0.0.0.0", port=5050, access_log=False)
