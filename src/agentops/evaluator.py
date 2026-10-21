"""
AgentOps Semantic Evaluator (RAG Triad & Hallucination Detector)
Primary Responsibility: Evaluates retrieval quality and generation grounding at runtime.
Calculates:
  1. Faithfulness Score (0.0 - 1.0): Degree to which claims in the answer are supported by the context.
  2. Context Relevance Score (0.0 - 1.0): Semantic alignment between the query and retrieved context.
  3. Answer Relevance Score (0.0 - 1.0): Degree to which the answer addresses the user query.
  4. Hallucination Flag (bool): True if answer makes unsupported factual claims despite context.
"""

import re
import numpy as np
from sentence_transformers import SentenceTransformer

class SemanticEvaluator:
    def __init__(self, embedding_model: SentenceTransformer = None):
        if embedding_model:
            self.model = embedding_model
        else:
            self.model = SentenceTransformer('all-MiniLM-L6-v2')

    def split_into_sentences(self, text: str) -> list[str]:
        if not text:
            return []
        # Split on sentence terminals while keeping acronyms/numbers mostly intact
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    def evaluate_rag_triad(self, query: str, context: list, answer: str) -> dict:
        """
        Runs lightweight, local semantic evaluation without requiring external API calls.
        Returns metrics normalized between 0.0 and 1.0.
        """
        if not context:
            # If no context was retrieved, check if agent properly abstained
            is_abstaining = "sufficient information" in answer.lower() or "don't have" in answer.lower()
            return {
                "faithfulness": 1.0 if is_abstaining else 0.0,
                "context_relevance": 0.0,
                "answer_relevance": 0.8 if is_abstaining else 0.2,
                "hallucination_detected": not is_abstaining,
                "grounding_status": "ABSTAINED_ACCURATE" if is_abstaining else "UNGROUNDED_HALLUCINATION"
            }

        context_texts = [c.get("content", "") for c in context]
        full_context = " ".join(context_texts)
        
        # 1. Context Relevance: Average similarity between query and retrieved chunks
        query_vec = self.model.encode([query])[0]
        chunk_vecs = self.model.encode(context_texts)
        
        # Cosine similarity for normalized vectors: dot product
        def cosine_sim(a, b):
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        
        context_relevance_scores = [cosine_sim(query_vec, cv) for cv in chunk_vecs]
        context_relevance = max(0.0, min(1.0, float(np.mean(context_relevance_scores))))

        # 2. Answer Relevance: Semantic similarity between query and the generated answer
        answer_vec = self.model.encode([answer])[0]
        answer_relevance = max(0.0, min(1.0, cosine_sim(query_vec, answer_vec)))

        # 3. Faithfulness (Claim-level grounding):
        # Extract statements from answer and verify their maximum similarity against any context chunk
        answer_sentences = self.split_into_sentences(answer)
        if not answer_sentences:
            faithfulness = 1.0
        else:
            sentence_vecs = self.model.encode(answer_sentences)
            supported_count = 0
            sentence_scores = []
            
            for s_vec in sentence_vecs:
                # Find best matching chunk
                max_sim = max([cosine_sim(s_vec, cv) for cv in chunk_vecs]) if chunk_vecs.size else 0.0
                sentence_scores.append(max_sim)
                # If sentence has similarity >= 0.50 to at least one chunk, it's considered grounded
                if max_sim >= 0.50:
                    supported_count += 1
            
            faithfulness = max(0.0, min(1.0, float(supported_count / len(answer_sentences))))

        # Hallucination detection heuristic
        # If faithfulness < 0.65 while context was provided, flag hallucination
        hallucination_detected = faithfulness < 0.65

        grounding_status = "FULLY_GROUNDED" if faithfulness >= 0.80 else ("PARTIALLY_GROUNDED" if faithfulness >= 0.60 else "HALLUCINATED")

        return {
            "faithfulness": round(faithfulness, 3),
            "context_relevance": round(context_relevance, 3),
            "answer_relevance": round(answer_relevance, 3),
            "hallucination_detected": hallucination_detected,
            "grounding_status": grounding_status
        }
