"""
Knowledge Base Retriever Module
Primary Responsibility: Executes semantic similarity searches against the FAISS index to retrieve context.
Why it exists: To isolate retrieval logic from the API and LLM layers, making it easy to swap FAISS for Neo4j later.
"""
import os
import faiss
import json
import numpy as np
from datetime import datetime
from sentence_transformers import SentenceTransformer

from src.agentops.telemetry import tracker

VECTOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "vector_store")

class FAISSRetriever:
    def __init__(self):
        # We assume index and metadata exist (Phase 2 completed)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.read_index(os.path.join(VECTOR_DIR, "faiss.index"))
        with open(os.path.join(VECTOR_DIR, "metadata.json"), 'r') as f:
            data = json.load(f)
            self.chunks = data["chunks"]
            self.metadata = data["metadata"]

    def retrieve(self, query: str, trace_id: str, top_k: int = 2) -> list:
        start_time = datetime.now()
        
        query_vector = self.model.encode([query])
        distances, indices = self.index.search(np.array(query_vector).astype('float32'), top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                results.append({
                    "content": self.chunks[idx],
                    "metadata": self.metadata[idx],
                    "distance": float(distances[0][i])
                })
        
        tracker.emit_span(
            trace_id=trace_id,
            span_type="retrieve_context",
            start_time=start_time,
            end_time=datetime.now(),
            metadata={"top_k": top_k, "num_results": len(results)}
        )
        return results
