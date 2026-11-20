#!/bin/bash
# ==============================================================================
# AgentOps Project - Automated Launcher Script
# Starts Infrastructure, FastAPI Gateway, Streamlit UI, AgentDashboard & Grafana
# ==============================================================================

if [ -f "/Applications/anaconda3/bin/python3.13" ]; then
    PYTHON_EXEC="/Applications/anaconda3/bin/python3.13"
else
    PYTHON_EXEC="python3"
fi

echo "🚀 Starting AgentOps Infrastructure with $PYTHON_EXEC..."

# 1. Start MySQL (powers Grafana SQL dashboards)
brew services start mysql 2>/dev/null

# 2. Start Tempo & OpenTelemetry Collector (Docker)
docker compose up -d

# 3. Check / Start Ollama if not running
if ! pgrep -x "ollama" > /dev/null; then
    echo "🦙 Starting Ollama server in background..."
    ollama serve > /dev/null 2>&1 &
    sleep 2
fi

echo "✅ Infrastructure is UP."
echo "--------------------------------------------------"
echo "🌐 Starting Core Application Services..."

# 4. Start FastAPI Backend Gateway (Port 8000)
$PYTHON_EXEC -m uvicorn src.agent.api:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
echo "   - FastAPI Backend Gateway: http://localhost:8000 (PID: $BACKEND_PID)"

# 5. Start Alert Receiver / AgentDashboard (Port 5050)
$PYTHON_EXEC alert_receiver.py > dashboard.log 2>&1 &
ALERT_PID=$!
echo "   - (N) AgentDashboard ☯︎:   http://localhost:5050 (PID: $ALERT_PID)"

# 6. Start Streamlit Chatbot Frontend (Port 8501)
$PYTHON_EXEC -m streamlit run ui/app.py --server.port 8501 --server.headless true > streamlit.log 2>&1 &
STREAMLIT_PID=$!
echo "   - Streamlit Admission Chatbot: http://localhost:8501 (PID: $STREAMLIT_PID)"

echo "--------------------------------------------------"
echo "📊 Monitoring & Observability URLs:"
echo "   - Grafana Native Dashboard: http://localhost:3000/d/agentops_metrics_v1"
echo "   - AgentDashboard Console:   http://localhost:5050"
echo "   - Public Chatbot Tunnel:    Run: npx cloudflared tunnel --url http://localhost:8501"
echo "--------------------------------------------------"
echo "💡 To stop all services anytime, run: ./stop_services.sh"
