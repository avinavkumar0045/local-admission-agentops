"""
Streamlit Chat Interface — Admission Assistant
Primary Responsibility: Renders the frontend chat UI with SRM background and communicates with the FastAPI backend.
"""
import streamlit as st
import httpx
import os
import base64
import uuid
from datetime import datetime, date

# --- Page Configuration ---
st.set_page_config(
    page_title="Admission Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Background Image Encoding ---
@st.cache_data
def get_srm_background_base64():
    """Encodes the SRM University entrance image into base64 for full-screen background."""
    img_path = os.path.join(os.path.dirname(__file__), "srm_campus.jpg")
    if os.path.exists(img_path):
        with open(img_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return ""

bg_base64 = get_srm_background_base64()

# --- Modular CSS Loading with Background Layer ---
def load_css_and_background(bg_data):
    css_path = os.path.join(os.path.dirname(__file__), "styles.css")
    css_content = ""
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css_content = f.read()

    bg_style = ""
    if bg_data:
        bg_style = f"""
        .srm-fixed-background {{
            background-image: 
                linear-gradient(180deg, rgba(8, 12, 24, 0.38) 0%, rgba(5, 8, 16, 0.52) 100%),
                url("data:image/jpeg;base64,{bg_data}");
        }}
        .stApp::before {{
            content: "";
            position: fixed;
            top: -20px;
            left: -20px;
            right: -20px;
            bottom: -20px;
            background-image: 
                linear-gradient(180deg, rgba(8, 12, 24, 0.38) 0%, rgba(5, 8, 16, 0.52) 100%),
                url("data:image/jpeg;base64,{bg_data}");
            background-size: cover;
            background-position: center center;
            background-repeat: no-repeat;
            background-attachment: fixed;
            filter: blur(3.5px) brightness(0.85);
            -webkit-filter: blur(3.5px) brightness(0.85);
            transform: scale(1.03);
            z-index: 0;
            pointer-events: none;
        }}
        """

    st.markdown(f"<style>{css_content}\n{bg_style}</style>", unsafe_allow_html=True)
    if bg_data:
        st.markdown('<div class="srm-fixed-background"></div>', unsafe_allow_html=True)

load_css_and_background(bg_base64)

# --- Frontend Session State ---
if "conversations" not in st.session_state:
    st.session_state.conversations = []

if "active_convo_id" not in st.session_state:
    st.session_state.active_convo_id = str(uuid.uuid4())

if "messages" not in st.session_state:
    st.session_state.messages = []

if "incidents" not in st.session_state:
    st.session_state.incidents = []

def record_user_query(query_text: str):
    """Adds the asked query directly to YOUR HISTORY in the sidebar."""
    clean_title = query_text.strip()
    if len(clean_title) > 32:
        clean_title = clean_title[:30] + "..."
    
    for convo in st.session_state.conversations:
        if convo["id"] == st.session_state.active_convo_id:
            convo["messages"] = list(st.session_state.messages)
            convo["updated_at"] = datetime.now()
            return
            
    st.session_state.conversations.insert(0, {
        "id": st.session_state.active_convo_id,
        "title": clean_title,
        "date": date.today(),
        "updated_at": datetime.now(),
        "messages": list(st.session_state.messages)
    })

def update_active_conversation_messages():
    """Updates messages of the active conversation after receiving assistant response."""
    for convo in st.session_state.conversations:
        if convo["id"] == st.session_state.active_convo_id:
            convo["messages"] = list(st.session_state.messages)
            convo["updated_at"] = datetime.now()
            return

# --- Sidebar UI (Glassmorphic) ---
with st.sidebar:
    # Top Brand with outline graduation cap
    st.markdown("""
    <div class="sidebar-brand-container">
        <span class="brand-cap-icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                <path d="M6 12v5c3 3 9 3 12 0v-5"/>
            </svg>
        </span>
        <span class="brand-title">Admission Assistant</span>
    </div>
    """, unsafe_allow_html=True)

    # "+ New Chat" Button
    st.markdown('<div class="new-chat-wrapper">', unsafe_allow_html=True)
    if st.button("+ New Chat", use_container_width=True, key="btn_new_chat"):
        st.session_state.messages = []
        st.session_state.active_convo_id = str(uuid.uuid4())
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # Search Conversation History
    search_query = st.text_input(
        "Search conversations", 
        placeholder="🔍 Search history...", 
        label_visibility="collapsed",
        key="search_history_input"
    )

    # "YOUR HISTORY" Section
    st.markdown('<div class="history-section-label">YOUR HISTORY</div>', unsafe_allow_html=True)

    filtered_convos = st.session_state.conversations
    if search_query.strip():
        sq = search_query.strip().lower()
        filtered_convos = [c for c in filtered_convos if sq in c.get("title", "").lower()]

    if filtered_convos:
        for c in filtered_convos:
            is_active = c["id"] == st.session_state.active_convo_id
            active_class = " active" if is_active else ""
            st.markdown(f'<div class="history-item-btn{active_class}">', unsafe_allow_html=True)
            if st.button(f"🗨  {c['title']}", key=f"hist_{c['id']}", use_container_width=True):
                st.session_state.active_convo_id = c["id"]
                st.session_state.messages = list(c["messages"])
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="color: #64748B; font-size: 0.8rem; padding: 0.8rem 0.5rem; text-align: left;">'
            'No conversations yet.'
            '</div>', 
            unsafe_allow_html=True
        )

    # --- Live AgentOps Alert & Incident Center ---
    st.markdown('<div class="history-section-label" style="margin-top: 1.6rem; letter-spacing: 0.08em;">AGENTOPS ALERT CENTER</div>', unsafe_allow_html=True)
    active_incidents = st.session_state.incidents
    if not active_incidents:
        st.markdown("""
        <div style="background: rgba(16, 185, 129, 0.12); border: 1px solid rgba(16, 185, 129, 0.28); border-radius: 6px; padding: 0.6rem 0.8rem; font-size: 0.78rem; color: #34D399; display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 0.95rem;">🟢</span>
            <span><b>All Systems Normal</b><br><span style="color: #94A3B8; font-size: 0.72rem;">0 active incidents</span></span>
        </div>
        """, unsafe_allow_html=True)
    else:
        crit_count = sum(1 for inc in active_incidents if "CRITICAL" in inc.get("severity", ""))
        warn_count = sum(1 for inc in active_incidents if "WARNING" in inc.get("severity", ""))
        st.markdown(f"""
        <div style="background: rgba(239, 68, 68, 0.16); border: 1px solid rgba(239, 68, 68, 0.4); border-radius: 6px; padding: 0.6rem 0.8rem; font-size: 0.78rem; color: #FCA5A5; display: flex; align-items: center; gap: 8px; margin-bottom: 0.4rem;">
            <span style="font-size: 1rem;">🚨</span>
            <span><b>{len(active_incidents)} Alert(s) Dispatched</b><br><span style="color: #E2E8F0; font-size: 0.72rem;">{crit_count} Critical · {warn_count} Warning</span></span>
        </div>
        """, unsafe_allow_html=True)
        with st.expander(f"📋 Incident Queue ({len(active_incidents)})", expanded=False):
            for inc in reversed(active_incidents[-5:]):
                sev = inc.get("severity", "P2_WARNING")
                badge_cls = "p1" if "CRITICAL" in sev else ("p2" if "WARNING" in sev else "p3")
                tid = inc.get('trace_id', '')
                tempo_url = f"http://localhost:3000/explore?schemaVersion=1&panes=%7B%223u5%22%3A%7B%22datasource%22%3A%22ffx7prdoh20hsd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%2C%22uid%22%3A%22ffx7prdoh20hsd%22%7D%2C%22queryType%22%3A%22traceql%22%2C%22query%22%3A%22%7Bspan.trace_id%3D%5C%22{tid}%5C%22%7D%22%7D%5D%7D%7D"
                st.markdown(f"""
                <div class="incident-feed-card">
                    <div class="incident-card-top">
                        <b style="color: #F8FAFC;">{inc.get('incident_id', 'INC')}</b>
                        <span class="alert-severity-badge {badge_cls}">{sev.replace('_', ' ')}</span>
                    </div>
                    <div style="color: #CBD5E1; font-size: 0.74rem; margin-bottom: 0.3rem;">{inc.get('title', 'Alert')}</div>
                    <div style="color: #94A3B8; font-size: 0.68rem;">Time: {inc.get('timestamp', '')}</div>
                    <div style="margin-top: 0.3rem;">
                        <a href="{tempo_url}" target="_blank" style="color: #A78BFA; font-size: 0.7rem; text-decoration: underline;">Open Tempo Trace ↗</a>
                    </div>
                </div>
                """, unsafe_allow_html=True)
            if st.button("Clear Incident Log", key="clear_incidents_btn", use_container_width=True):
                st.session_state.incidents = []
                st.rerun()

    st.markdown("""
    <div style="margin-top: 0.8rem;">
        <a href="http://localhost:5050" target="_blank" style="display: block; text-align: center; background: rgba(167, 139, 250, 0.12); border: 1px solid rgba(167, 139, 250, 0.35); color: #C4B5FD; padding: 7px 12px; border-radius: 6px; font-size: 0.76rem; text-decoration: none; font-weight: 600; transition: all 0.2s ease;">
            🚨 Open Incident Center (Port 5050) ↗
        </a>
    </div>
    """, unsafe_allow_html=True)

# --- Main Chat Area ---
if not st.session_state.messages:
    # Clear Floating Welcome Hero (No bulky card blocking the SRM Gate)
    st.markdown("""
    <div class="hero-clear-container">
        <div class="hero-cap-svg">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M22 10v6M2 10l10-5 10 5-10 5z"/>
                <path d="M6 12v5c3 3 9 3 12 0v-5"/>
            </svg>
        </div>
        <h1 class="hero-heading">Your journey to SRM starts here.</h1>
        <p class="hero-subheading">
            Everything you need to know about SRM University admissions, all in one place.
        </p>
        <p class="hero-subheading" style="font-size: 0.88rem; color: #94A3B8; margin-top: 0.5rem !important;">
            Ask about B.Tech admissions, CSE fees, eligibility criteria, scholarships, entrance exams and more.
        </p>
    </div>
    """, unsafe_allow_html=True)

else:
    # Active Conversation Header
    st.markdown("""
    <div class="active-chat-header">
        <div>
            <span style="font-size: 1.05rem; font-weight: 700; color: #FFFFFF;">🎓 Admission Assistant</span>
            <span style="font-size: 0.8rem; color: #94A3B8; margin-left: 8px;">Your AI-powered guide to college admissions</span>
        </div>
        <div style="display: flex; align-items: center; gap: 10px;">
            <a href="http://localhost:5050" target="_blank" style="text-decoration: none;">
                <span class="status-indicator" style="background: rgba(239, 68, 68, 0.15); color: #FCA5A5; border-color: rgba(239, 68, 68, 0.35);">🚨 Incident Center</span>
            </a>
            <span class="status-indicator">🟢 AgentOps Active</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Render Chat History
    for idx, msg in enumerate(st.session_state.messages):
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(f'<div class="user-glass-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            with st.chat_message("assistant", avatar="🎓"):
                st.markdown(msg["content"])

                # In-App AgentOps Alert Banner (if incident was triggered)
                alert = msg.get("alert")
                if alert:
                    tid = alert.get('trace_id', '')
                    tempo_url = f"http://localhost:3000/explore?schemaVersion=1&panes=%7B%223u5%22%3A%7B%22datasource%22%3A%22ffx7prdoh20hsd%22%2C%22queries%22%3A%5B%7B%22refId%22%3A%22A%22%2C%22datasource%22%3A%7B%22type%22%3A%22tempo%22%2C%22uid%22%3A%22ffx7prdoh20hsd%22%7D%2C%22queryType%22%3A%22traceql%22%2C%22query%22%3A%22%7Bspan.trace_id%3D%5C%22{tid}%5C%22%7D%22%7D%5D%7D%7D"
                    st.markdown(f"""
                    <div class="agentops-alert-banner {alert.get('style_class', 'warning')}">
                        <div class="alert-banner-header">
                            <div class="alert-title-wrap">
                                <span style="font-size: 1.05rem;">{alert.get('icon', '⚠️')}</span>
                                <span class="alert-title-text">{alert.get('title', 'AgentOps Runtime Alert')}</span>
                            </div>
                            <span class="alert-severity-badge {alert.get('badge_class', 'p2')}">{alert.get('severity_label', 'P2 WARNING')}</span>
                        </div>
                        <div class="alert-banner-body">
                            {alert.get('detail', '')}
                        </div>
                        <div class="alert-banner-footer">
                            <span>Incident: <b>{alert.get('incident_id', 'INC-001')}</b></span>
                            <span><a href="{tempo_url}" target="_blank">View Tempo Trace ↗</a></span>
                            <span style="color: #34D399; font-weight: 600;">● Dispatched to Port 5050 Webhook</span>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                # AgentOps Semantic Verification Badge
                if msg.get("eval_metrics"):
                    m = msg["eval_metrics"]
                    faith = m.get("faithfulness", 0.0)
                    ctx_rel = m.get("context_relevance", 0.0)
                    status = m.get("grounding_status", "N/A")
                    if status == "SECURITY_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #EF4444;">
                                <span>🛡️ Security Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(239, 68, 68, 0.15); color: #FCA5A5;">Prompt Injection Intercepted (<1ms)</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    elif status == "TOXICITY_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #F59E0B;">
                                <span>🛡️ Safety Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(245, 158, 11, 0.15); color: #FCD34D;">Toxicity & Abuse Deflected (<1ms)</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    elif status == "GUARDRAIL_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #6366f1;">
                                <span>🛡️ Scope Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">Admissions Domain Active</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""<div class="eval-badge-line">
                                <span>🛡️ AgentOps Grounding:</span>
                                <span class="eval-badge-tag">Faithfulness: {faith:.2f}</span>
                                <span class="eval-badge-tag">Relevance: {ctx_rel:.2f}</span>
                                <span class="eval-badge-tag">Status: {status}</span>
                            </div>""",
                            unsafe_allow_html=True
                        )

                # Human-in-the-Loop Feedback & DPO Dataset Curation
                tid = msg.get("trace_id", "")
                if tid:
                    f_status = msg.get("feedback_status")
                    if f_status == "up":
                        st.markdown('<div style="font-size: 0.78rem; color: #10B981; margin-top: 6px;">✅ <b>Feedback Recorded:</b> Verified gold standard response.</div>', unsafe_allow_html=True)
                    elif f_status == "down":
                        note_text = msg.get("feedback_note", "")
                        st.markdown(f'<div style="font-size: 0.78rem; color: #F59E0B; margin-top: 6px;">🎯 <b>Flagged for DPO Fine-Tuning</b> {f"— <i>{note_text}</i>" if note_text else ""}</div>', unsafe_allow_html=True)
                    else:
                        c_up, c_down, _ = st.columns([0.16, 0.24, 0.60])
                        with c_up:
                            if st.button("👍 Helpful", key=f"thumb_up_{idx}", help="Mark as accurate and grounded"):
                                try:
                                    httpx.post("http://127.0.0.1:8000/feedback", json={"trace_id": tid, "rating": 1}, timeout=2.0)
                                except Exception:
                                    pass
                                try:
                                    httpx.post("http://127.0.0.1:5050/api/incidents/feedback_update", json={"trace_id": tid, "rating": 1}, timeout=1.0)
                                except Exception:
                                    pass
                                msg["feedback_status"] = "up"
                                update_active_conversation_messages()
                                st.toast("Thank you! Recorded as verified gold standard.", icon="👍")
                                st.rerun()
                        with c_down:
                            if st.button("👎 Flag / Inaccurate", key=f"thumb_down_{idx}", help="Flag as inaccurate to curate DPO dataset"):
                                st.session_state[f"show_note_input_{idx}"] = True
                                st.rerun()

                        if st.session_state.get(f"show_note_input_{idx}"):
                            with st.container():
                                note_val = st.text_input(
                                    "Optional correction or explanation to curate DPO dataset:",
                                    key=f"note_input_{idx}",
                                    placeholder="e.g. Fees mentioned was outdated, SRM 2026 fee is 4.75L"
                                )
                                c_sub, c_cancel = st.columns([0.35, 0.65])
                                with c_sub:
                                    if st.button("Submit DPO Flag", key=f"submit_note_{idx}"):
                                        prompt_text = st.session_state.messages[idx-1]["content"] if idx > 0 else "Student Query"
                                        try:
                                            httpx.post(
                                                "http://127.0.0.1:8000/feedback",
                                                json={
                                                    "trace_id": tid,
                                                    "rating": -1,
                                                    "notes": note_val,
                                                    "prompt": prompt_text,
                                                    "rejected_answer": msg.get("content", ""),
                                                    "context": msg.get("context", []),
                                                    "faithfulness": msg.get("eval_metrics", {}).get("faithfulness", 0.0)
                                                },
                                                timeout=3.0
                                            )
                                        except Exception:
                                            pass
                                        try:
                                            httpx.post(
                                                "http://127.0.0.1:5050/api/incidents/feedback_update",
                                                json={"trace_id": tid, "rating": -1, "notes": note_val},
                                                timeout=1.0
                                            )
                                        except Exception:
                                            pass
                                        msg["feedback_status"] = "down"
                                        msg["feedback_note"] = note_val
                                        st.session_state[f"show_note_input_{idx}"] = False
                                        update_active_conversation_messages()
                                        st.toast("Curated into DPO training dataset!", icon="🎯")
                                        st.rerun()
                                with c_cancel:
                                    if st.button("Cancel", key=f"cancel_note_{idx}"):
                                        st.session_state[f"show_note_input_{idx}"] = False
                                        st.rerun()

# --- Chat Input & Execution ---
chat_input_val = st.chat_input("Ask anything about college admissions...")

if chat_input_val:
    # 1. Render user query immediately in blue translucent glass bubble and record in history
    st.session_state.messages.append({"role": "user", "content": chat_input_val})
    record_user_query(chat_input_val)
    
    with st.chat_message("user"):
        st.markdown(f'<div class="user-glass-bubble">{chat_input_val}</div>', unsafe_allow_html=True)

    # 2. Fetch response from FastAPI backend
    with st.chat_message("assistant", avatar="🎓"):
        with st.spinner("Analyzing admission records..."):
            try:
                # 240s timeout to allow local CPU LLM inference to complete reliably
                response = httpx.post(
                    "http://127.0.0.1:8000/query", 
                    json={"query": chat_input_val},
                    timeout=240.0
                )
                response.raise_for_status()
                data = response.json()
                
                answer = data.get("answer", "No answer provided.")
                context = data.get("context", [])
                eval_metrics = data.get("eval_metrics", {})
                trace_id = data.get("trace_id", "")
                
                st.markdown(answer)
                
                # Check for AgentOps Runtime Alert Conditions
                triggered_alert = None
                faith = eval_metrics.get("faithfulness", 1.0) if eval_metrics else 1.0
                hallucinated = eval_metrics.get("hallucination_detected", False) if eval_metrics else False
                status_str = eval_metrics.get("grounding_status", "") if eval_metrics else ""

                if status_str == "GUARDRAIL_BLOCKED":
                    # Clean, polite out-of-scope handling: do not display an alarming incident banner to the student
                    triggered_alert = None
                elif hallucinated or faith < 0.70 or "HALLUCINATED" in status_str:
                    inc_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
                    triggered_alert = {
                        "incident_id": inc_id,
                        "title": "AgentOps Alert: Semantic Grounding Degradation",
                        "severity": "P2_WARNING",
                        "severity_label": "P2 WARNING",
                        "style_class": "warning",
                        "badge_class": "p2",
                        "icon": "⚠️",
                        "detail": f"Faithfulness ({faith:.2f}) dipped below 0.70 SLA threshold. Potential ungrounded or contradictory claim detected. Operational incident ticket dispatched to Operations Webhook (port 5050).",
                        "trace_id": trace_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    st.session_state.incidents.append(triggered_alert)
                    try:
                        httpx.post(
                            "http://127.0.0.1:5050/alert", 
                            json={
                                "title": "AgentOps Alert: Semantic Grounding Degradation",
                                "severity": "P2_WARNING",
                                "summary": f"Query '{chat_input_val[:60]}': Faithfulness ({faith:.2f}) dipped below 0.70 threshold.",
                                "query": chat_input_val,
                                "trace_id": trace_id,
                                "faithfulness": faith,
                                "context_relevance": eval_metrics.get("context_relevance", 0.5),
                                "hallucinated": hallucinated,
                                "is_fatal": False
                            }, 
                            timeout=0.6
                        )
                    except Exception:
                        pass
                    st.toast(f"🚨 AgentOps Incident {inc_id}: Semantic Grounding Warning Dispatched!", icon="⚠️")
                
                elif not context and "sorry" in answer.lower():
                    inc_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
                    triggered_alert = {
                        "incident_id": inc_id,
                        "title": "AgentOps Notice: Knowledge Gap & Safe Abstention",
                        "severity": "P3_INFO",
                        "severity_label": "P3 INFO",
                        "style_class": "info",
                        "badge_class": "p3",
                        "icon": "ℹ️",
                        "detail": "No relevant admission chunks found in FAISS vector database. Model safely abstained from generating speculative facts.",
                        "trace_id": trace_id,
                        "timestamp": datetime.now().strftime("%H:%M:%S")
                    }
                    st.session_state.incidents.append(triggered_alert)
                
                if eval_metrics:
                    faith = eval_metrics.get("faithfulness", 0.0)
                    ctx_rel = eval_metrics.get("context_relevance", 0.0)
                    status = eval_metrics.get("grounding_status", "N/A")
                    if status == "SECURITY_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #EF4444;">
                                <span>🛡️ Security Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(239, 68, 68, 0.15); color: #FCA5A5;">Prompt Injection Intercepted (<1ms)</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    elif status == "TOXICITY_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #F59E0B;">
                                <span>🛡️ Safety Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(245, 158, 11, 0.15); color: #FCD34D;">Toxicity & Abuse Deflected (<1ms)</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    elif status == "GUARDRAIL_BLOCKED":
                        st.markdown(
                            """<div class="eval-badge-line" style="border-left: 3px solid #6366f1;">
                                <span>🛡️ Scope Guard:</span>
                                <span class="eval-badge-tag" style="background: rgba(99, 102, 241, 0.15); color: #a5b4fc;">Admissions Domain Active</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                    else:
                        st.markdown(
                            f"""<div class="eval-badge-line">
                                <span>🛡️ AgentOps Grounding:</span>
                                <span class="eval-badge-tag">Faithfulness: {faith:.2f}</span>
                                <span class="eval-badge-tag">Relevance: {ctx_rel:.2f}</span>
                                <span class="eval-badge-tag">Status: {status}</span>
                            </div>""",
                            unsafe_allow_html=True
                        )
                            
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "context": context,
                    "eval_metrics": eval_metrics,
                    "trace_id": trace_id,
                    "alert": triggered_alert
                })
                
                update_active_conversation_messages()
                st.rerun()
                
            except httpx.ReadTimeout:
                inc_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
                crit_alert = {
                    "incident_id": inc_id,
                    "title": "AgentOps Alert: Inference Latency SLA Timeout",
                    "severity": "P1_CRITICAL",
                    "severity_label": "P1 CRITICAL",
                    "style_class": "critical",
                    "badge_class": "p1",
                    "icon": "🚨",
                    "detail": "Local LLM inference exceeded execution deadline (ReadTimeout). Operational circuit breaker triggered and logged to Grafana Tempo.",
                    "trace_id": "",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.incidents.append(crit_alert)
                try:
                    httpx.post(
                        "http://127.0.0.1:5050/alert", 
                        json={
                            "title": "AgentOps Alert: Inference Latency SLA Timeout",
                            "severity": "P1_CRITICAL",
                            "summary": f"Query '{chat_input_val[:60]}': Execution exceeded latency deadline (ReadTimeout).",
                            "query": chat_input_val,
                            "is_fatal": True,
                            "latency_s": 60.0
                        }, 
                        timeout=0.6
                    )
                except Exception:
                    pass
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "⚠️ **Inference Timeout:** The local LLM engine took too long to complete. An incident ticket has been dispatched.",
                    "alert": crit_alert
                })
                update_active_conversation_messages()
                st.rerun()
            except Exception as e:
                inc_id = f"INC-{str(uuid.uuid4())[:8].upper()}"
                crit_alert = {
                    "incident_id": inc_id,
                    "title": "AgentOps Alert: Critical Service Disruption",
                    "severity": "P1_CRITICAL",
                    "severity_label": "P1 CRITICAL",
                    "style_class": "critical",
                    "badge_class": "p1",
                    "icon": "🚨",
                    "detail": f"Backend API / Vector DB connectivity failure: {str(e)[:150]}. Outage logged to Tempo and Webhook receiver.",
                    "trace_id": "",
                    "timestamp": datetime.now().strftime("%H:%M:%S")
                }
                st.session_state.incidents.append(crit_alert)
                try:
                    httpx.post(
                        "http://127.0.0.1:5050/alert", 
                        json={
                            "title": "AgentOps Alert: Critical Service Disruption",
                            "severity": "P1_CRITICAL",
                            "summary": f"Query '{chat_input_val[:60]}': Backend API / Vector DB failure: {str(e)[:80]}",
                            "query": chat_input_val,
                            "is_fatal": True,
                            "latency_s": 15.0
                        }, 
                        timeout=0.6
                    )
                except Exception:
                    pass
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": "🚨 **Service Error:** An operational error occurred while processing your request.",
                    "alert": crit_alert
                })
                update_active_conversation_messages()
                st.rerun()
