"""
AgentOps Telemetry Tracker
Primary Responsibility: Emits traces via OpenTelemetry to the local OTel Collector.
"""
import uuid
from datetime import datetime
import json
import sys
import os
import mysql.connector

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace import NoOpTracerProvider
from opentelemetry.sdk.resources import Resource

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.config import AGENTOPS_ENABLED, DB_HOST, DB_USER, DB_PASSWORD, DB_NAME

if AGENTOPS_ENABLED:
    resource = Resource(attributes={"service.name": "admission-agent"})
    provider = TracerProvider(resource=resource)
    
    # Export to the local OTel Collector (via gRPC on 4317)
    otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
    processor = BatchSpanProcessor(otlp_exporter)
    provider.add_span_processor(processor)
    trace.set_tracer_provider(provider)
else:
    trace.set_tracer_provider(NoOpTracerProvider())

tracer = trace.get_tracer("agentops.tracer")

# --- Keep Legacy MySQL Telemetry Tracker for Evaluation/Ground Truth ---
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
                self.enabled = False

    def emit_span(self, trace_id, span_type, start_time, end_time, status="success", error_msg=None, metadata=None):
        if not self.enabled or not self.conn: return
        span_id = str(uuid.uuid4())
        duration_ms = (end_time - start_time).total_seconds() * 1000
        metadata_str = json.dumps(metadata) if metadata else None
        self._ensure_trace_exists(trace_id)
        try:
            cursor = self.conn.cursor()
            query = """INSERT INTO spans (span_id, trace_id, span_type, start_time, end_time, duration_ms, status, error_message, metadata) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            cursor.execute(query, (span_id, trace_id, span_type, start_time, end_time, duration_ms, status, error_msg, metadata_str))
            cursor.close()
        except: pass

    def _ensure_trace_exists(self, trace_id):
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT trace_id FROM traces WHERE trace_id = %s", (trace_id,))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO sessions (session_id) VALUES (%s)", (trace_id,))
                cursor.execute("INSERT INTO traces (trace_id, session_id, query, status) VALUES (%s, %s, %s, %s)", (trace_id, trace_id, 'Agent execution', 'active'))
            cursor.close()
        except: pass

tracker = TelemetryTracker()
