"""
AgentOps Human-in-the-Loop (HITL) & Auto-DPO Dataset Collector
Captures thumbs-down / flagged agent outputs paired with retrieved ground truth context,
curating ready-to-train Direct Preference Optimization (DPO) datasets in HuggingFace TRL format.
"""
import os
import json
import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

DPO_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "dpo")
RAW_LOG_PATH = os.path.join(DPO_DIR, "flagged_interactions.jsonl")
DPO_DATASET_PATH = os.path.join(DPO_DIR, "dpo_train_dataset.jsonl")
RATINGS_LOG_PATH = os.path.join(DPO_DIR, "ratings_log.jsonl")

os.makedirs(DPO_DIR, exist_ok=True)

class DPOCollector:
    def __init__(self):
        self.raw_log_path = RAW_LOG_PATH
        self.dpo_dataset_path = DPO_DATASET_PATH
        self.ratings_log_path = RATINGS_LOG_PATH

    def record_rating(self, trace_id: str, rating: int, notes: Optional[str] = None):
        """Persists every human interaction rating (+1 or -1) to disk for resilient CSAT tracking."""
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "rating": rating,
            "notes": notes
        }
        with open(self.ratings_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def curate_interaction(
        self,
        trace_id: str,
        prompt: str,
        rejected_answer: str,
        context: Optional[List[Dict[str, Any]]] = None,
        notes: Optional[str] = None,
        faithfulness: float = 0.0,
        grounding_status: str = "FLAGGED_BY_USER",
        chosen_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processes a flagged or thumbs-down interaction and curates a DPO pair:
        - prompt: The student query
        - rejected: The imperfect or ungrounded agent answer
        - chosen: Synthesized from highest-relevance context chunk or student correction note
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        
        # Determine the gold-standard 'chosen' reference
        chosen_answer = chosen_override
        source_doc = "unknown_reference"

        if not chosen_answer:
            if notes and len(notes.strip()) > 15:
                # Student provided a concrete correction
                chosen_answer = f"Correction based on verified feedback: {notes.strip()}"
                source_doc = "student_expert_correction"
            elif context and len(context) > 0:
                # Extract ground-truth excerpt from top retrieved context chunk
                top_chunk = context[0]
                chunk_content = top_chunk.get("content", "").strip()
                source_doc = top_chunk.get("metadata", {}).get("source", "verified_context.pdf")
                chosen_answer = (
                    f"Based on official admission records ({source_doc}): "
                    f"{chunk_content[:350]}..."
                )
            else:
                chosen_answer = (
                    "I currently do not have verified admission records to answer this specific query accurately. "
                    "Please refer directly to the official university admissions portal."
                )
                source_doc = "abstention_policy"

        # 1. Full Audit Record (flagged_interactions.jsonl)
        audit_record = {
            "record_id": f"DPO-{str(uuid.uuid4())[:8].upper()}",
            "trace_id": trace_id,
            "timestamp": now_iso,
            "prompt": prompt,
            "rejected_answer": rejected_answer,
            "chosen_answer": chosen_answer,
            "student_notes": notes or "",
            "source_doc": source_doc,
            "faithfulness": faithfulness,
            "grounding_status": grounding_status,
            "status": "CURATED_FOR_ALIGNMENT"
        }

        with open(self.raw_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record) + "\n")

        # 2. Standard HuggingFace TRL DPO Training Format (dpo_train_dataset.jsonl)
        dpo_pair = {
            "prompt": prompt,
            "chosen": chosen_answer,
            "rejected": rejected_answer,
            "system": "You are the official Indian College Admissions Assistant. Provide strictly factual, grounded information.",
            "source": source_doc,
            "trace_id": trace_id
        }

        with open(self.dpo_dataset_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(dpo_pair) + "\n")

        return audit_record

    def get_summary_stats(self) -> Dict[str, Any]:
        """Returns statistics on curated DPO records."""
        total_flagged = 0
        recent_records = []
        if os.path.exists(self.raw_log_path):
            with open(self.raw_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        total_flagged += 1
                        try:
                            recent_records.append(json.loads(line))
                        except:
                            pass
        return {
            "total_curated_dpo_pairs": total_flagged,
            "dataset_file": self.dpo_dataset_path,
            "recent_records": recent_records[-10:][::-1]  # Latest 10 records descending
        }

dpo_collector = DPOCollector()
