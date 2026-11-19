"""
Knowledge Base Ingestion Script
Primary Responsibility: Reads raw and processed markdown, PDF, CSV, and Excel files,
chunks them with sliding window overlap, generates semantic embeddings, and saves them to a FAISS index.
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

# Set offline environment variables to prevent Hugging Face Hub timeouts
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

# Add src to path to import telemetry
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.agentops.telemetry import tracker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DATA_DIRS = [
    os.path.join(BASE_DIR, "data", "raw"),
    os.path.join(BASE_DIR, "data", "processed"),
    os.path.join(BASE_DIR, "data", "samples"),
]
VECTOR_DIR = os.path.join(BASE_DIR, "data", "vector_store")

def sliding_window_chunker(text: str, max_words: int = 120, overlap_words: int = 30) -> list:
    """
    Sliding window chunker with word overlap.
    Preserves boundary continuity for course titles, fee schedules, and admission eligibility.
    """
    words = str(text).split()
    if not words:
        return []
    if len(words) <= max_words:
        return [" ".join(words)]
        
    step = max(1, max_words - overlap_words)
    chunks = []
    for i in range(0, len(words), step):
        chunk = " ".join(words[i:i + max_words])
        if chunk.strip():
            chunks.append(chunk)
        if i + max_words >= len(words):
            break
    return chunks

def extract_text_from_file(file_path: str) -> str:
    ext = os.path.splitext(file_path)[1].lower()
    text = ""
    try:
        if ext in ['.md', '.txt']:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
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
    print("==================================================")
    print("🚀 Starting Knowledge Base Re-Chunking & Ingestion")
    print("==================================================")
    trace_id = str(uuid.uuid4())
    
    # 1. Load Embedding Model
    model_start = datetime.now()
    print("📦 Loading local SentenceTransformer ('all-MiniLM-L6-v2')...")
    model = SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)
    tracker.emit_span(
        trace_id=trace_id, span_type="load_embedding_model", 
        start_time=model_start, end_time=datetime.now(), metadata={"model": "all-MiniLM-L6-v2"}
    )
    
    # 2. Collect All Eligible Documents
    chunk_start = datetime.now()
    all_chunks = []
    metadata = []
    processed_files = set()
    
    valid_extensions = {'.pdf', '.md', '.txt', '.csv', '.xlsx'}
    
    for folder in DATA_DIRS:
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            for file in sorted(files):
                if file.startswith('.') or file.endswith(('.zip', '.gz', '.pyc')):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if ext not in valid_extensions:
                    continue
                    
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, BASE_DIR)
                
                # Avoid ingesting duplicate basenames across processed and raw if identical
                if file in processed_files and "processed" in root:
                    continue
                processed_files.add(file)
                
                text = extract_text_from_file(file_path)
                if not text.strip():
                    print(f"  ⚠️  [Empty or unreadable]: {rel_path}")
                    continue
                
                chunks = sliding_window_chunker(text, max_words=120, overlap_words=30)
                print(f"  📄 [Processed] {rel_path} -> {len(chunks)} chunks")
                
                for i, chunk in enumerate(chunks):
                    all_chunks.append(chunk)
                    metadata.append({
                        "source": file,
                        "rel_path": rel_path,
                        "chunk_index": i
                    })
                    
    print(f"\n📊 Summary: Processed {len(processed_files)} distinct files, created {len(all_chunks)} chunks.")
    
    tracker.emit_span(
        trace_id=trace_id, span_type="document_chunking", 
        start_time=chunk_start, end_time=datetime.now(),
        metadata={"total_files": len(processed_files), "total_chunks": len(all_chunks)}
    )
    
    if not all_chunks:
        print("❌ No documents found to ingest.")
        return

    # 3. Embed Chunks
    print(f"\n🧠 Generating embeddings for {len(all_chunks)} chunks...")
    embed_start = datetime.now()
    embeddings = model.encode(all_chunks, batch_size=128, show_progress_bar=True)
    tracker.emit_span(
        trace_id=trace_id, span_type="generate_embeddings", 
        start_time=embed_start, end_time=datetime.now(), metadata={"embedding_shape": str(embeddings.shape)}
    )
    
    # 4. Save to FAISS Index
    print("💾 Saving FAISS index and metadata...")
    faiss_start = datetime.now()
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings).astype('float32'))
    
    os.makedirs(VECTOR_DIR, exist_ok=True)
    faiss.write_index(index, os.path.join(VECTOR_DIR, "faiss.index"))
    
    with open(os.path.join(VECTOR_DIR, "metadata.json"), 'w') as f:
        json.dump({"chunks": all_chunks, "metadata": metadata}, f, indent=2)
        
    tracker.emit_span(
        trace_id=trace_id, span_type="save_faiss_index", 
        start_time=faiss_start, end_time=datetime.now(), metadata={"index_path": "data/vector_store/faiss.index"}
    )

    print(f"✅ Ingestion complete! FAISS index updated with {len(all_chunks)} chunks across {len(processed_files)} source files.")

if __name__ == "__main__":
    ingest_documents()
