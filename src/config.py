import os
from dotenv import load_dotenv

load_dotenv()

# AgentOps Telemetry Toggle (The Core Experiment Control)
AGENTOPS_ENABLED = os.getenv("AGENTOPS_ENABLED", "true").lower() == "true"

# MySQL Database Config
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "agentops_db")

# LLM Config
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen2.5-coder:latest")
