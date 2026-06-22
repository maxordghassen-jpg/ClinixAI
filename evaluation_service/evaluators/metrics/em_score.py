"""
Exact Match (EM) metric.

Standard QA metric: 1 if normalized candidate == normalized reference, else 0.
Normalization: lowercase, strip punctuation, collapse whitespace.
"""

from evaluators.metrics.text_normalizer import normalize


def compute_exact_match(candidate: str, reference: str) -> float:
    """Returns 1.0 if normalized strings are identical, 0.0 otherwise."""
    if not candidate or not reference:
        return 0.0
    return 1.0 if normalize(candidate) == normalize(reference) else 0.0
