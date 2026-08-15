"""
Knowledge Base Ingestion Script
Primary Responsibility: Reads raw markdown files, chunks them, generates semantic embeddings, and saves them to a FAISS index.
Why it exists: To construct the retrieval foundation (Knowledge Base) for the RAG agent, while simultaneously emitting telemetry spans.
"""
import os
import glob
from datetime import datetime
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import uuid

# Add src to path to import telemetry
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.agentops.telemetry import tracker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")
VECTOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "vector_store")

def simple_chunker(text, max_words=100):
    """Simple word-based chunker for markdown files."""
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        chunks.append(chunk)
    return chunks

def ingest_documents():
    print("Starting document ingestion...")
    trace_id = str(uuid.uuid4())
    ingest_start = datetime.now()
    
    # 1. Load Model
    model_start = datetime.now()
    print("Loading embedding model (this may take a few seconds to download on first run)...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    tracker.emit_span(
        trace_id=trace_id, 
        span_type="load_embedding_model", 
        start_time=model_start, 
        end_time=datetime.now(),
        metadata={"model": "all-MiniLM-L6-v2"}
    )
    
    # 2. Read and Chunk Documents
    chunk_start = datetime.now()
    all_chunks = []
    metadata = []
    
    md_files = glob.glob(os.path.join(DATA_DIR, "*.md"))
    for file_path in md_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
            filename = os.path.basename(file_path)
            chunks = simple_chunker(text)
            for i, chunk in enumerate(chunks):
                all_chunks.append(chunk)
                metadata.append({"source": filename, "chunk_index": i})
                
    tracker.emit_span(
        trace_id=trace_id, 
        span_type="document_chunking", 
        start_time=chunk_start, 
        end_time=datetime.now(),
        metadata={"total_files": len(md_files), "total_chunks": len(all_chunks)}
    )
    
    if not all_chunks:
        print("No documents found to ingest.")
        return

    # 3. Embed Chunks
    print(f"Embedding {len(all_chunks)} chunks...")
    embed_start = datetime.now()
    embeddings = model.encode(all_chunks)
    tracker.emit_span(
        trace_id=trace_id, 
        span_type="generate_embeddings", 
        start_time=embed_start, 
        end_time=datetime.now(),
        metadata={"embedding_shape": str(embeddings.shape)}
    )
    
    # 4. Save to FAISS
    faiss_start = datetime.now()
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    faiss.write_index(index, os.path.join(VECTOR_DIR, "faiss.index"))
    
    # Save metadata separately so we can map vectors back to text
    with open(os.path.join(VECTOR_DIR, "metadata.json"), 'w') as f:
        json.dump({"chunks": all_chunks, "metadata": metadata}, f)
        
    tracker.emit_span(
        trace_id=trace_id, 
        span_type="save_faiss_index", 
        start_time=faiss_start, 
        end_time=datetime.now(),
        metadata={"index_path": "data/vector_store/faiss.index"}
    )

    print(f"Ingestion complete. Added {len(all_chunks)} chunks to FAISS index.")

if __name__ == "__main__":
    ingest_documents()
