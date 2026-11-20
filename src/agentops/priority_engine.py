"""
Composite AgentOps Priority Scoring (CAPS) Engine
Implements the research-grade mathematical formula for incident prioritization in RAG agents:

Formula:
    Phi = min(100, [w1 * I + w2 * S] * B * U)

Where:
    - I: Infrastructure Loss (System fatal errors & latency SLA breach)
    - S: Semantic Grounding Loss (RAG Triad Faithfulness deficit + Hallucinations)
    - B: Domain Entity Liability (Regulatory impact: Fees/Refund vs Cutoffs vs Campus)
    - U: Human Feedback Multiplier (Student thumbs-up/down amplification)
"""
import re
from typing import Dict, Any, Optional

W1 = 0.40  # Weight for Infrastructure
W2 = 0.60  # Weight for Semantic Grounding

# Keywords for Domain Entity Liability Classification (B)
STATUTORY_KEYWORDS = [
    r"fee", r"fees", r"tuition", r"refund", r"scholarship", r"deposit",
    r"ugc", r"aicte", r"accreditation", r"fine", r"penalty", r"payment", r"cost",
    r"affidavit", r"ragging", r"reservation", r"quota", r"waiver", r"charges"
]

ELIGIBILITY_KEYWORDS = [
    r"eligibility", r"cutoff", r"cut-off", r"rank", r"jee", r"neet", r"srmjeee",
    r"marks", r"percentage", r"percentile", r"board", r"criteria", r"deadline"
]

class CAPSEngine:
    def __init__(self, latency_sla_s: float = 10.0, latency_timeout_s: float = 60.0):
        self.latency_sla_s = latency_sla_s
        self.latency_timeout_s = latency_timeout_s

    def compute_b_liability(self, query: str) -> float:
        """Determines Domain Entity Liability (B) multiplier from query semantics."""
        q_lower = query.lower()
        for kw in STATUTORY_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', q_lower):
                return 1.5  # High Statutory Risk (Fees, Refunds, Regulations)
        for kw in ELIGIBILITY_KEYWORDS:
            if re.search(r'\b' + kw + r'\b', q_lower):
                return 1.2  # Medium Statutory Risk (Cutoffs, Entrance Exams)
        return 0.8  # Low Risk (Campus life, sports, mess, hostel amenities)

    def compute_u_multiplier(
        self, 
        feedback_rating: Optional[int], 
        feedback_notes: Optional[str] = None, 
        hallucinated: bool = False,
        b_liability: float = 1.0,
        faithfulness: float = 1.0
    ) -> float:
        """
        Determines Human Feedback Multiplier (U).
        - Thumbs-down (-1): Amplifies priority (1.4 with note, 1.2 without).
        - Thumbs-up (+1): Mitigates false alarms (0.6).
        - Deceptive Confirmation Protection: If a user upvotes a severe statutory violation (B=1.5, faith < 0.35),
          the risk is amplified (1.3) because a human was misled by false legal/regulatory claims.
        """
        if feedback_rating == -1:
            if feedback_notes and len(feedback_notes.strip()) > 5:
                return 1.4  # Explicit human correction provided
            return 1.2  # Thumbs-down unannotated
        elif feedback_rating == 1:
            if hallucinated and b_liability >= 1.5 and faithfulness < 0.35:
                return 1.3  # Deceptive Confirmation: User was misled by high-liability hallucination
            return 0.6  # Verified helpful (de-escalates false alarms)
        return 1.0  # Unrated (neutral)

    def compute_i_loss(self, is_fatal: bool, latency_s: float) -> float:
        """Calculates Infrastructure Loss (I in [0, 100])."""
        if is_fatal:
            return 100.0
        if latency_s <= self.latency_sla_s:
            return 0.0
        # Linear scaling from SLA (10s) to timeout (60s)
        normalized_excess = (latency_s - self.latency_sla_s) / max(1.0, (self.latency_timeout_s - self.latency_sla_s))
        return round(min(1.0, max(0.0, normalized_excess)) * 50.0, 2)

    def compute_s_loss(self, faithfulness: float, hallucinated: bool, context_relevance: float) -> float:
        """Calculates Semantic Grounding Loss (S in [0, 100])."""
        f = max(0.0, min(1.0, faithfulness))
        h = 1.0 if hallucinated else 0.0
        c_rel = max(0.0, min(1.0, context_relevance))

        raw_s = (0.50 * (1.0 - f)) + (0.30 * h) + (0.20 * (1.0 - c_rel))
        return round(raw_s * 100.0, 2)

    def evaluate(
        self,
        query: str,
        is_fatal: bool = False,
        latency_s: float = 0.0,
        faithfulness: float = 1.0,
        hallucinated: bool = False,
        context_relevance: float = 1.0,
        feedback_rating: Optional[int] = None,
        feedback_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Computes the Composite AgentOps Priority Score (CAPS):
        Phi = min(100, [0.4 * I + 0.6 * S] * B * U)
        """
        I = self.compute_i_loss(is_fatal=is_fatal, latency_s=latency_s)
        S = self.compute_s_loss(faithfulness=faithfulness, hallucinated=hallucinated, context_relevance=context_relevance)
        B = self.compute_b_liability(query=query)
        U = self.compute_u_multiplier(
            feedback_rating=feedback_rating, 
            feedback_notes=feedback_notes, 
            hallucinated=hallucinated,
            b_liability=B,
            faithfulness=faithfulness
        )

        core_loss = (W1 * I) + (W2 * S)
        phi = round(min(100.0, max(0.0, core_loss * B * U)), 1)

        # Priority Tier Thresholds
        if phi >= 75.0 or is_fatal:
            severity = "P1_CRITICAL"
        elif phi >= 40.0:
            severity = "P2_WARNING"
        else:
            severity = "P3_INFO"

        return {
            "caps_score": phi,
            "severity": severity,
            "components": {
                "I": I,
                "S": S,
                "B": B,
                "U": U
            },
            "formula_repr": f"min(100, [0.4×{I:.1f} + 0.6×{S:.1f}] × {B} × {U}) = {phi}"
        }

caps_engine = CAPSEngine()
