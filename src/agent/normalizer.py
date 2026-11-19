"""
Query Normalization and Spelling Correction Engine
===================================================
Inspired by:
"Graph NLU enabled question answering system" (Heliyon 2021)
- Section 4.3: Custom unit for correcting spelling errors before entity/intent extraction
- Section 4.4 & Algorithm 1: Levenshtein distance string matching with thresholding against domain entities

Primary Responsibility:
Corrects common typos (e.g., 'fess' -> 'fees', 'eligiblity' -> 'eligibility') and normalizes domain synonyms
(e.g., 'branch' -> 'campus', 'ktr' -> 'kattankulathur') in under 2ms before passing queries to FAISS/Fast-Path.
"""

import time
import re
from typing import Tuple, Dict, Any

# Canonical domain vocabulary for admission queries
CANONICAL_VOCABULARY = {
    # Core admission concepts
    "fees", "fee", "tuition", "eligibility", "eligible", "admission", "admissions",
    "scholarship", "scholarships", "counseling", "counselling", "refund", "deposit",
    "percentage", "percent", "aggregate", "criteria", "deadline", "application",
    "founder", "concession", "waiver", "registration", "brochure", "curriculum",
    "autonomous", "institutions", "colleges", "universities", "university",
    "hostel", "mess", "caution", "quota", "reservation", "ranking", "rank", "marks",
    
    # Campus and place entities
    "kattankulathur", "ramapuram", "vadapalani", "tiruchirappalli", "chennai",
    "delhi", "california", "india",
    
    # Examination entities
    "srmjeee", "srmjee", "jee", "mains", "advanced", "neet", "comedk", "cat", "mat", "xat",
    
    # Disciplines & degrees
    "computer", "science", "engineering", "btech", "mtech", "mba", "physics",
    "chemistry", "mathematics", "pcm", "b.tech", "m.tech", "tech",
    "hotel", "catering", "law", "management", "program", "programs", "undergraduate", "postgraduate", "llb", "bba"
}

# Domain synonym & abbreviation mapper
SYNONYM_MAP = {
    "branch": "campus",
    "branches": "campuses",
    "ktr": "kattankulathur",
    "rmp": "ramapuram",
    "vdp": "vadapalani",
    "comp sci": "computer science",
    "cost": "fees",
    "pricing": "fees",
    "price": "fee"
}

# Explicit high-frequency admission typos for O(1) instant correction
COMMON_TYPOS = {
    "fess": "fees",
    "feee": "fees",
    "elgibility": "eligibility",
    "eligibilty": "eligibility",
    "scholorship": "scholarship",
    "scholership": "scholarship",
    "admision": "admission",
    "counceling": "counseling",
    "counselling": "counseling",
    "percntage": "percentage",
    "kattankulathr": "kattankulathur",
    "ramapuran": "ramapuram"
}

def levenshtein_distance(s1: str, s2: str) -> int:
    """Calculates Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def match_closest_word(word: str) -> str:
    """
    Finds the closest canonical domain word using Levenshtein distance.
    Applies distance <= 1 for short words (length 4-6) and distance <= 2 for longer words (length > 6).
    Words of length <= 3 are left untouched to prevent false corrections of short acronyms.
    """
    w_lower = word.lower()
    
    # 1. Exact canonical or common typo
    if w_lower in CANONICAL_VOCABULARY:
        return word
    if w_lower in COMMON_TYPOS:
        return COMMON_TYPOS[w_lower]

    if len(w_lower) <= 3:
        return word

    max_dist = 2 if len(w_lower) > 6 else 1

    best_match = None
    min_dist = max_dist + 1

    for canon in CANONICAL_VOCABULARY:
        if abs(len(w_lower) - len(canon)) > max_dist:
            continue

        dist = levenshtein_distance(w_lower, canon)
        if dist < min_dist:
            min_dist = dist
            best_match = canon

    if min_dist <= max_dist and best_match:
        # Match case
        if word.isupper():
            return best_match.upper()
        elif word.istitle():
            return best_match.title()
        return best_match

    return word

class QueryNormalizer:
    def __init__(self):
        pass

    def normalize(self, query: str) -> Tuple[str, Dict[str, Any]]:
        """
        Normalizes a user query by applying:
        1. Synonym mapping (e.g. 'branch' -> 'campus')
        2. Levenshtein edit distance spell-correction (e.g. 'fess' -> 'fees')
        Returns: (normalized_query_string, metadata_dict)
        """
        t0 = time.time()
        tokens = re.findall(r"[\w\.]+|[^\w\s]", query)
        
        corrections = {}
        synonyms_applied = {}
        normalized_tokens = []

        for token in tokens:
            t_lower = token.lower()
            
            # Check for punctuation
            if not token.isalnum() and not ('.' in token and token.replace('.', '').isalnum()):
                normalized_tokens.append(token)
                continue

            # 1. Apply Synonym Mapping
            if t_lower in SYNONYM_MAP:
                mapped = SYNONYM_MAP[t_lower]
                synonyms_applied[token] = mapped
                normalized_tokens.append(mapped)
                continue

            # 2. Apply Spell Checking (Levenshtein Distance)
            corrected = match_closest_word(token)
            if corrected.lower() != t_lower:
                corrections[token] = corrected
                normalized_tokens.append(corrected)
            else:
                normalized_tokens.append(token)

        # Reconstruct query cleanly
        normalized_query = " ".join(normalized_tokens)
        # Clean up space before punctuation
        normalized_query = re.sub(r'\s+([?,.!:])', r'\1', normalized_query)

        elapsed_ms = (time.time() - t0) * 1000

        metadata = {
            "original_query": query,
            "normalized_query": normalized_query,
            "corrections": corrections,
            "synonyms_applied": synonyms_applied,
            "latency_ms": round(elapsed_ms, 3),
            "modified": bool(corrections or synonyms_applied)
        }

        return normalized_query, metadata
