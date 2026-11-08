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
        <div>
            <span class="status-indicator">🟢 AgentOps Active</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Render Chat History
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(f'<div class="user-glass-bubble">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            with st.chat_message("assistant", avatar="🎓"):
                st.markdown(msg["content"])
                
                # Explainability Expander
                if "context" in msg and msg["context"]:
                    with st.expander("🔍 View Sources (Explainability)"):
                        for idx, chunk in enumerate(msg["context"]):
                            source_file = chunk.get("metadata", {}).get("source", "Official Institutional Record")
                            dist = chunk.get("distance", 0.0)
                            st.markdown(f"**Source {idx+1}:** `{source_file}` *(Distance: {dist:.2f})*")
                            st.write(chunk.get("content", ""))

                # AgentOps Semantic Verification Badge
                if msg.get("eval_metrics"):
                    m = msg["eval_metrics"]
                    faith = m.get("faithfulness", 0.0)
                    ctx_rel = m.get("context_relevance", 0.0)
                    status = m.get("grounding_status", "N/A")
                    st.markdown(
                        f"""<div class="eval-badge-line">
                            <span>🛡️ AgentOps Grounding:</span>
                            <span class="eval-badge-tag">Faithfulness: {faith:.2f}</span>
                            <span class="eval-badge-tag">Relevance: {ctx_rel:.2f}</span>
                            <span class="eval-badge-tag">Status: {status}</span>
                        </div>""",
                        unsafe_allow_html=True
                    )

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
                if context:
                    with st.expander("🔍 View Sources (Explainability)"):
                        for idx, chunk in enumerate(context):
                            source_file = chunk.get("metadata", {}).get("source", "Official Institutional Record")
                            dist = chunk.get("distance", 0.0)
                            st.markdown(f"**Source {idx+1}:** `{source_file}` *(Distance: {dist:.2f})*")
                            st.write(chunk.get("content", ""))
                
                if eval_metrics:
                    faith = eval_metrics.get("faithfulness", 0.0)
                    ctx_rel = eval_metrics.get("context_relevance", 0.0)
                    status = eval_metrics.get("grounding_status", "N/A")
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
                    "trace_id": trace_id
                })
                
                update_active_conversation_messages()
                st.rerun()
                
            except httpx.ReadTimeout:
                st.error("The local LLM took too long to respond. Please try again.")
            except Exception as e:
                st.error(f"Backend API error: {e}")
