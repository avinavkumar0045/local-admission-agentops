"""
AgentOps Telemetry Tracker
Primary Responsibility: Provides the interface for the agent to emit traces and spans into a MySQL database.
Why it exists: To fulfill the 'Instrumentation-by-Design' requirement, allowing observability to be permanently recorded for the Phase 6 evaluation.
"""
import uuid
from datetime import datetime
import json
import sys
import os
import mysql.connector

# Add src to path if needed for running locally
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.config import AGENTOPS_ENABLED, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

class TelemetryTracker:
    def __init__(self):
        self.enabled = AGENTOPS_ENABLED
        self.conn = None
        if self.enabled:
            try:
                self.conn = mysql.connector.connect(
                    host=DB_HOST,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    database=DB_NAME
                )
                self.conn.autocommit = True
            except Exception as e:
                print(f"[AGENTOPS WARNING] Failed to connect to MySQL: {e}")
                self.enabled = False

    def emit_span(self, trace_id: str, span_type: str, start_time: datetime, end_time: datetime, status: str = "success", error_msg: str = None, metadata: dict = None):
        if not self.enabled or not self.conn:
            return

        span_id = str(uuid.uuid4())
        duration_ms = (end_time - start_time).total_seconds() * 1000
        metadata_str = json.dumps(metadata) if metadata else None
        
        # Ensure trace exists (dummy trace creation for now if missing)
        self._ensure_trace_exists(trace_id)
        
        try:
            cursor = self.conn.cursor()
            query = """
                INSERT INTO spans 
                (span_id, trace_id, span_type, start_time, end_time, duration_ms, status, error_message, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            values = (span_id, trace_id, span_type, start_time, end_time, duration_ms, status, error_msg, metadata_str)
            cursor.execute(query, values)
            cursor.close()
            print(f"[AGENTOPS SPAN SAVED TO DB] {span_type} ({duration_ms:.2f}ms)")
        except Exception as e:
            print(f"[AGENTOPS WARNING] Failed to insert span: {e}")

    def _ensure_trace_exists(self, trace_id: str):
        """Creates a dummy trace record if it doesn't exist to satisfy foreign key constraints."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT trace_id FROM traces WHERE trace_id = %s", (trace_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO sessions (session_id) VALUES (%s)", (trace_id,))
                cursor.execute("INSERT INTO traces (trace_id, session_id, query, status) VALUES (%s, %s, %s, %s)", (trace_id, trace_id, 'Agent execution', 'active'))
            cursor.close()
        except Exception as e:
            # Ignore if already exists or fails
            pass

tracker = TelemetryTracker()
