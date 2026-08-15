"""
Streamlit Chat Interface
Primary Responsibility: Renders the frontend chat UI and communicates with the FastAPI backend.
Why it exists: To provide a professional, user-friendly interface for students to interact with the RAG agent.
"""
import streamlit as st
import httpx
import os

# --- Page Configuration ---
st.set_page_config(
    page_title="Admission AgentOps",
    page_icon="🎓",
    layout="centered"
)

# --- Modular CSS Loading ---
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

load_css()

# --- App Header ---
st.title("🎓 Admission Assistant")
st.caption("Powered by Local Qwen, FAISS, and AgentOps Telemetry")

# --- Session State Management ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# --- Render Chat History ---
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "context" in msg and msg["context"]:
            with st.expander("🔍 View Sources (Explainability)"):
                for idx, chunk in enumerate(msg["context"]):
                    st.markdown(f"**Source {idx+1}: {chunk['metadata']['source']}**")
                    st.caption(f"Relevance Distance: {chunk['distance']:.2f}")
                    st.write(chunk['content'])

# --- Chat Input & Backend Logic ---
if prompt := st.chat_input("Ask a question about admissions (e.g., B.Tech eligibility)..."):
    
    # Render user query immediately
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Fetch response from FastAPI backend
    with st.chat_message("assistant"):
        with st.spinner("Analyzing admission policies..."):
            try:
                # 120s timeout to match the backend Qwen processing limits
                response = httpx.post(
                    "http://127.0.0.1:8000/query", 
                    json={"query": prompt},
                    timeout=130.0
                )
                response.raise_for_status()
                data = response.json()
                
                answer = data.get("answer", "No answer provided.")
                context = data.get("context", [])
                
                st.markdown(answer)
                if context:
                    with st.expander("🔍 View Sources (Explainability)"):
                        for idx, chunk in enumerate(context):
                            st.markdown(f"**Source {idx+1}: {chunk['metadata']['source']}**")
                            st.caption(f"Relevance Distance: {chunk['distance']:.2f}")
                            st.write(chunk['content'])
                            
                st.session_state.messages.append({
                    "role": "assistant", 
                    "content": answer,
                    "context": context
                })
                
            except httpx.ReadTimeout:
                st.error("The local LLM took too long to respond. Please try again.")
            except Exception as e:
                st.error(f"Backend API error: {e}")
