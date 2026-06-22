"""
Exact Set Match (ESM) metric.

Used in multi-answer QA: treats both candidate and reference as bags of tokens.
Score = Jaccard similarity between the two token sets.
Partial credit for partially overlapping answers.
"""

import re
from evaluators.metrics.text_normalizer import normalize


def _token_set(text: str) -> set[str]:
    tokens = re.split(r"\s+", normalize(text))
    return {t for t in tokens if t}


def compute_exact_set_match(candidate: str, reference: str) -> float:
    """
    Jaccard similarity between candidate and reference token sets.
    Returns float ∈ [0, 1].
    """
    if not candidate or not reference:
        return 0.0
    cand_set = _token_set(candidate)
    ref_set  = _token_set(reference)
    if not cand_set and not ref_set:
        return 1.0
    intersection = len(cand_set & ref_set)
    union        = len(cand_set | ref_set)
    return round(intersection / union, 4) if union else 0.0
