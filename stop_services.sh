#!/bin/bash
# ==============================================================================
# AgentOps Project - Stop All Services Script
# ==============================================================================

echo "🛑 Stopping AgentOps application processes..."

# Kill processes by port
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:8501 | xargs kill -9 2>/dev/null
lsof -ti:5050 | xargs kill -9 2>/dev/null

echo "✅ FastAPI (8000), Streamlit (8501), and AgentDashboard (5050) stopped."
echo "💡 To also stop Docker containers, run: docker compose down"
