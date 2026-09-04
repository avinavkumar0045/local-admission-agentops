"""
Knowledge Base Retriever Module
Primary Responsibility: Executes semantic similarity searches against the FAISS index to retrieve context.
"""
import os
import faiss
import json
import numpy as np
from datetime import datetime, timezone
from sentence_transformers import SentenceTransformer
from opentelemetry import trace

from src.agentops.telemetry import tracer, tracker

VECTOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "vector_store")

class FAISSRetriever:
    def __init__(self):
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.read_index(os.path.join(VECTOR_DIR, "faiss.index"))
        with open(os.path.join(VECTOR_DIR, "metadata.json"), 'r') as f:
            data = json.load(f)
            self.chunks = data["chunks"]
            self.metadata = data["metadata"]

    def retrieve(self, query: str, trace_id: str, top_k: int = 2) -> list:
        start_time = datetime.now(timezone.utc)
        
        with tracer.start_as_current_span("retrieval") as ret_span:
            ret_span.set_attribute("knowledge_base_version", "v1.0")
            
            with tracer.start_as_current_span("embedding_generation") as emb_span:
                emb_span.set_attribute("embedding_model", "all-MiniLM-L6-v2")
                query_vector = self.model.encode([query])
                
            with tracer.start_as_current_span("faiss.search") as search_span:
                # --- PHASE 8: FAILURE INJECTION ---
                # We simulate a catastrophic database outage where FAISS becomes unreachable.
                failure_simulation = False 
                
                if failure_simulation:
                    search_span.set_attribute("failure_class", "RETRIEVAL_DB_OUTAGE")
                    search_span.set_status(trace.Status(trace.StatusCode.ERROR, "Simulated FAISS Database Outage"))
                    tracker.emit_span(trace_id, "retrieve_context", start_time, datetime.now(timezone.utc), "failure", "Simulated FAISS Database Outage")
                    raise ConnectionError("FATAL: Unable to connect to FAISS Vector Database on port 5432.")
                # -----------------------------------

                distances, indices = self.index.search(np.array(query_vector).astype('float32'), top_k)
            
            # This won't run because of the simulated crash, but kept for structure
            with tracer.start_as_current_span("context.selection") as ctx_span:
                results = []
                # ... normal logic ...
                
        return []
