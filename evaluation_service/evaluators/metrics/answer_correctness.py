"""
Answer Correctness metric.

Combines:
  - Semantic similarity (sentence-transformers cosine, 0.6 weight)
  - Token F1 overlap with reference answer (0.4 weight)

Designed for open-domain QA where exact match is too strict.
Uses the multilingual MiniLM model so FR/AR work out-of-box.
"""

import logging
import re
import string

logger = logging.getLogger(__name__)

_st_model = None


def _load_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            logger.warning("[AnswerCorrectness] sentence-transformers unavailable: %s", e)
    return _st_model


def _token_set(text: str) -> set[str]:
    text = text.lower().translate(str.maketrans("", "", string.punctuation))
    return {t for t in re.split(r"\s+", text.strip()) if t}


def _token_f1(candidate: str, reference: str) -> float:
    pred_tokens = _token_set(candidate)
    gold_tokens = _token_set(reference)
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = len(pred_tokens & gold_tokens)
    if common == 0:
        return 0.0
    precision = common / len(pred_tokens)
    recall    = common / len(gold_tokens)
    return round(2 * precision * recall / (precision + recall), 4)


def _semantic_similarity(candidate: str, reference: str) -> float:
    import numpy as np
    model = _load_model()
    if model is None:
        return 0.5
    try:
        embs = model.encode([candidate, reference], show_progress_bar=False)
        norm = lambda v: v / (float(np.linalg.norm(v)) + 1e-9)
        return float(max(0.0, min(1.0, np.dot(norm(embs[0]), norm(embs[1])))))
    except Exception as e:
        logger.warning("[AnswerCorrectness] Semantic sim failed: %s", e)
        return 0.5


def compute_answer_correctness(candidate: str, reference: str) -> float:
    """
    Hybrid correctness score ∈ [0, 1].
    0.6 × semantic_similarity + 0.4 × token_f1
    """
    if not candidate or not reference:
        return 0.0
    sem  = _semantic_similarity(candidate, reference)
    tf1  = _token_f1(candidate, reference)
    return round(0.6 * sem + 0.4 * tf1, 4)
