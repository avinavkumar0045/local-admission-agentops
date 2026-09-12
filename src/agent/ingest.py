"""
Knowledge Base Ingestion Script
Primary Responsibility: Reads raw markdown, PDF, CSV, and Excel files, chunks them, generates semantic embeddings, and saves them to a FAISS index.
"""
import os
import glob
from datetime import datetime
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer
import json
import uuid
import pandas as pd
from pypdf import PdfReader

# Add src to path to import telemetry
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.agentops.telemetry import tracker

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "raw")
VECTOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "vector_store")

def simple_chunker(text, max_words=100):
    """Simple word-based chunker."""
    words = str(text).split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
        if chunk.strip():
            chunks.append(chunk)
    return chunks

def extract_text_from_file(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext == '.md' or ext == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                text = f.read()
        elif ext == '.pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        elif ext == '.csv':
            df = pd.read_csv(file_path)
            text = df.to_string(index=False)
        elif ext == '.xlsx':
            df = pd.read_excel(file_path)
            text = df.to_string(index=False)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return text

def ingest_documents():
    print("Starting document ingestion...")
    trace_id = str(uuid.uuid4())
    ingest_start = datetime.now()
    
    # 1. Load Model
    model_start = datetime.now()
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    tracker.emit_span(
        trace_id=trace_id, span_type="load_embedding_model", 
        start_time=model_start, end_time=datetime.now(), metadata={"model": "all-MiniLM-L6-v2"}
    )
    
    # 2. Read and Chunk Documents
    chunk_start = datetime.now()
    all_chunks = []
    metadata = []
    
    all_files = glob.glob(os.path.join(DATA_DIR, "*.*"))
    for file_path in all_files:
        print(f"Processing: {os.path.basename(file_path)}")
        text = extract_text_from_file(file_path)
        if not text.strip(): continue
        
        filename = os.path.basename(file_path)
        chunks = simple_chunker(text, max_words=150)
        for i, chunk in enumerate(chunks):
            all_chunks.append(chunk)
            metadata.append({"source": filename, "chunk_index": i})
                
    tracker.emit_span(
        trace_id=trace_id, span_type="document_chunking", 
        start_time=chunk_start, end_time=datetime.now(),
        metadata={"total_files": len(all_files), "total_chunks": len(all_chunks)}
    )
    
    if not all_chunks:
        print("No documents found to ingest.")
        return

    # 3. Embed Chunks
    print(f"Embedding {len(all_chunks)} chunks (this may take a minute for large files)...")
    embed_start = datetime.now()
    embeddings = model.encode(all_chunks)
    tracker.emit_span(
        trace_id=trace_id, span_type="generate_embeddings", 
        start_time=embed_start, end_time=datetime.now(), metadata={"embedding_shape": str(embeddings.shape)}
    )
    
    # 4. Save to FAISS
    faiss_start = datetime.now()
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    os.makedirs(VECTOR_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(VECTOR_DIR, "faiss.index"))
    
    # Save metadata
    with open(os.path.join(VECTOR_DIR, "metadata.json"), 'w') as f:
        json.dump({"chunks": all_chunks, "metadata": metadata}, f)
        
    tracker.emit_span(
        trace_id=trace_id, span_type="save_faiss_index", 
        start_time=faiss_start, end_time=datetime.now(), metadata={"index_path": "data/vector_store/faiss.index"}
    )

    print(f"Ingestion complete. Added {len(all_chunks)} chunks to FAISS index.")

if __name__ == "__main__":
    ingest_documents()
