"""
Phase 12: Offline Information Retrieval (IR) Benchmarking Harness
==================================================================
Evaluates the FAISS dense retrieval layer against a curated Golden Dataset.

Calculates:
1. HitRate@K (Recall@K): Fraction of queries where at least one target chunk was retrieved.
2. Precision@K: Fraction of retrieved top-K chunks that match the ground-truth document & topic.
3. MRR (Mean Reciprocal Rank): Position of the first relevant chunk (1/rank).
4. Average Retrieval Latency (ms): Microsecond-level dense vector search time.
"""

import os
import json
import time
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VECTOR_DIR = os.path.join(BASE_DIR, "data", "vector_store")
BENCHMARK_PATH = os.path.join(BASE_DIR, "benchmarks", "golden_dataset.json")
REPORT_PATH = os.path.join(BASE_DIR, "benchmarks", "benchmark_report.json")

def run_retrieval_benchmark(top_k_values=[1, 3, 5]):
    print("=" * 60)
    print("PHASE 12: OFFLINE RETRIEVAL EVALUATION (FAISS BENCHMARK)")
    print("=" * 60)

    # 1. Load Embedding Model & FAISS Index
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    
    print("Loading FAISS index & metadata...")
    index = faiss.read_index(os.path.join(VECTOR_DIR, "faiss.index"))
    with open(os.path.join(VECTOR_DIR, "metadata.json"), "r") as f:
        meta_data = json.load(f)
        chunks = meta_data["chunks"]
        metadata = meta_data["metadata"]

    print(f"Total Chunks in Vector Store: {len(chunks)} ({index.ntotal} vectors)")

    # 2. Load Golden Test Dataset
    with open(BENCHMARK_PATH, "r") as f:
        golden_set = json.load(f)
    print(f"Total Benchmark Queries: {len(golden_set)}\n")

    results_by_k = {}

    for k in top_k_values:
        total_queries = len(golden_set)
        hits = 0
        total_precision_sum = 0.0
        reciprocal_ranks = []
        latencies = []

        for item in golden_set:
            qid = item["id"]
            query = item["query"]
            target_source = item["target_source"].lower()
            keywords = [kw.lower() for kw in item.get("relevant_keywords", [])]

            # Measure vector search latency
            t0 = time.time()
            q_vec = model.encode([query]).astype("float32")
            distances, indices = index.search(q_vec, k)
            lat_ms = (time.time() - t0) * 1000
            latencies.append(lat_ms)

            retrieved_chunks = []
            for i in range(k):
                idx = int(indices[0][i])
                if idx < len(chunks):
                    retrieved_chunks.append({
                        "source": metadata[idx].get("source", "").lower(),
                        "content": chunks[idx].lower(),
                        "distance": float(distances[0][i])
                    })

            # Check relevance
            # A chunk is relevant if it comes from the target document OR matches 2+ keywords
            relevant_retrieved = 0
            first_relevant_rank = None

            for rank_idx, chunk in enumerate(retrieved_chunks):
                is_source_match = target_source in chunk["source"]
                matched_kw_count = sum(1 for kw in keywords if kw in chunk["content"])
                
                if is_source_match or matched_kw_count >= 2:
                    relevant_retrieved += 1
                    if first_relevant_rank is None:
                        first_relevant_rank = rank_idx + 1

            if relevant_retrieved > 0:
                hits += 1

            precision = relevant_retrieved / float(k)
            total_precision_sum += precision

            if first_relevant_rank:
                reciprocal_ranks.append(1.0 / first_relevant_rank)
            else:
                reciprocal_ranks.append(0.0)

        hit_rate = hits / float(total_queries)
        mean_precision = total_precision_sum / float(total_queries)
        mrr = float(np.mean(reciprocal_ranks))
        avg_latency = float(np.mean(latencies))

        results_by_k[f"top_{k}"] = {
            "hit_rate_recall": round(hit_rate, 4),
            "precision": round(mean_precision, 4),
            "mrr": round(mrr, 4),
            "avg_latency_ms": round(avg_latency, 2)
        }

        print(f"Results @ K={k}:")
        print(f"  - HitRate / Recall@{k} : {hit_rate * 100:.2f}% ({hits}/{total_queries})")
        print(f"  - Precision@{k}        : {mean_precision * 100:.2f}%")
        print(f"  - MRR@{k}              : {mrr:.4f}")
        print(f"  - Avg Search Latency   : {avg_latency:.2f} ms")
        print("-" * 50)

    # 3. Save Structured Report
    final_report = {
        "benchmark_dataset_size": len(golden_set),
        "total_indexed_chunks": len(chunks),
        "results": results_by_k,
        "evaluation_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    with open(REPORT_PATH, "w") as f:
        json.dump(final_report, f, indent=2)

    print(f"\n[OK] Phase 12 Evaluation Report successfully written to:\n     {REPORT_PATH}\n")
    return final_report

if __name__ == "__main__":
    run_retrieval_benchmark()
