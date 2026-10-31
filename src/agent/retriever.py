"""
Knowledge Base Retriever Module
Primary Responsibility: Executes semantic similarity searches against the FAISS index to retrieve context.
"""
import os
import faiss
import json
import re
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

    def retrieve(self, query: str, trace_id: str, top_k: int = 3) -> list:
        start_time = datetime.now(timezone.utc)
        
        with tracer.start_as_current_span("retrieval") as ret_span:
            ret_span.set_attribute("knowledge_base_version", "v1.0")
            ret_span.set_attribute("total_chunks_in_db", len(self.chunks))
            
            with tracer.start_as_current_span("embedding_generation") as emb_span:
                emb_span.set_attribute("embedding_model", "all-MiniLM-L6-v2")
                query_vector = self.model.encode([query])
                
            with tracer.start_as_current_span("faiss.search") as search_span:
                failure_simulation = False 
                if failure_simulation:
                    raise ConnectionError("FATAL: Unable to connect to FAISS Vector Database on port 5432.")

                # Search FAISS
                distances, indices = self.index.search(np.array(query_vector).astype('float32'), top_k)
            
            with tracer.start_as_current_span("context.selection") as ctx_span:
                candidate_results = []
                source_files = set()
                
                for i in range(top_k):
                    idx = int(indices[0][i])
                    dist = float(distances[0][i])
                    
                    if idx < len(self.chunks) and dist < 1.5:  # Arbitrary threshold
                        chunk_text = self.chunks[idx]
                        source = self.metadata[idx].get("source", "Unknown")
                        source_files.add(source)
                        
                        candidate_results.append({
                            "content": chunk_text,
                            "metadata": self.metadata[idx],
                            "distance": dist
                        })

                # --- SAGE-QA LTR Context Pruning ---
                # Prunes out filler lines to reduce prompt token size by ~40% for faster LLM generation
                results = []
                query_words = set(re.findall(r'\w+', query.lower()))
                for cand in candidate_results:
                    raw_lines = cand["content"].split("\n")
                    pruned_lines = []
                    for line in raw_lines:
                        line_stripped = line.strip()
                        if not line_stripped:
                            continue
                        line_words = set(re.findall(r'\w+', line_stripped.lower()))
                        # Keep line if it shares semantic tokens with query or carries admission facts
                        if (line_words & query_words) or any(k in line_stripped.lower() for k in ["fee", "eligib", "percent", "marks", "pcm", "exam", "rank", "quota", "seat", "date", "refund"]):
                            pruned_lines.append(line_stripped)
                    
                    # If pruning filtered too aggressively, preserve original chunk
                    final_content = "\n".join(pruned_lines) if len(pruned_lines) >= 2 else cand["content"]
                    results.append({
                        "content": final_content,
                        "metadata": cand["metadata"],
                        "distance": cand["distance"]
                    })
                
                # Add the exact source files and counts to the OpenTelemetry trace!
                ctx_span.set_attribute("documents_selected", len(results))
                ctx_span.set_attribute("source_files", json.dumps(list(source_files)))
                ctx_span.set_attribute("selection_threshold", 1.5)
                ctx_span.set_attribute("ltr_pruning_applied", True)
                
                # Emit legacy tracker
                tracker.emit_span(trace_id, "retrieve_context", start_time, datetime.now(timezone.utc), "success", None, {"sources": list(source_files)})
                
        return results
