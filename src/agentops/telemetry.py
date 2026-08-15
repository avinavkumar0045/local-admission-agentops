import uuid
from datetime import datetime
import json
import sys
import os

# Add src to path if needed for running locally
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.config import AGENTOPS_ENABLED

class TelemetryTracker:
    """
    Initial Telemetry Interface (Instrumentation-by-Design).
    In Phase 4, this will connect directly to MySQL and OpenTelemetry.
    """
    def __init__(self):
        self.enabled = AGENTOPS_ENABLED

    def emit_span(self, trace_id: str, span_type: str, start_time: datetime, end_time: datetime, status: str = "success", error_msg: str = None, metadata: dict = None):
        if not self.enabled:
            return

        span_id = str(uuid.uuid4())
        duration_ms = (end_time - start_time).total_seconds() * 1000
        
        span_data = {
            "span_id": span_id,
            "trace_id": trace_id,
            "span_type": span_type,
            "duration_ms": duration_ms,
            "status": status,
            "error": error_msg,
            "metadata": metadata
        }
        
        # For Phase 1-3, we print to console/log. Phase 4 will INSERT to MySQL.
        print(f"[AGENTOPS SPAN EMITTED] {json.dumps(span_data)}")
        
        # TODO: Phase 4 MySQL Insertion logic here
        
tracker = TelemetryTracker()
