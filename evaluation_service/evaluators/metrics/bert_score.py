"""
BERTScore semantic similarity evaluation.

Primary: bert-score package (contextual token-level embeddings, F1).
Fallback: sentence-transformers cosine similarity when bert-score is unavailable.

Use for: semantic similarity between candidate and reference responses.
Especially valuable for multilingual evaluation (FR/AR) where n-gram overlap
metrics like BLEU/ROUGE penalise valid paraphrases heavily.

NOT a replacement for LLM-as-a-Judge on workflow correctness — use in addition.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# BCP-47 → bert-score language code
_LANG_MAP: dict[str, str] = {
    "english": "en",
    "french":  "fr",
    "arabic":  "ar",
    "en":      "en",
    "fr":      "fr",
    "ar":      "ar",
}

# Lazy import — avoid pulling torch at module import time
_bert_score_fn   = None
_st_model        = None
_bert_available  = False

try:
    from bert_score import score as _bert_score_fn  # type: ignore
    _bert_available = True
    logger.info("[BERTScore] bert_score package available")
except ImportError:
    logger.info("[BERTScore] bert_score not installed — falling back to cosine similarity. "
                "Install with: pip install bert-score")


def _load_st_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
            logger.info("[BERTScore] Sentence-transformers fallback model loaded")
        except Exception as e:
            logger.warning("[BERTScore] Sentence-transformers unavailable: %s", e)
    return _st_model


def _cosine_fallback(candidate: str, reference: str) -> float:
    """Sentence-transformer cosine similarity as lightweight BERTScore proxy."""
    import numpy as np
    model = _load_st_model()
    if model is None:
        return 0.5  # both unavailable
    try:
        embs   = model.encode([candidate, reference], show_progress_bar=False)
        norm   = lambda v: v / (np.linalg.norm(v) + 1e-9)
        cosine = float(np.dot(norm(embs[0]), norm(embs[1])))
        return max(0.0, min(1.0, cosine))
    except Exception as e:
        logger.warning("[BERTScore] Cosine fallback failed: %s", e)
        return 0.5


def compute_bert_score(candidate: str, reference: str, language: str = "english") -> float:
    """
    Compute semantic similarity between candidate and reference.
    Returns F1 ∈ [0, 1].

    Multilingual: uses bert-base-multilingual-cased for non-English languages.
    """
    if not candidate or not reference:
        return 0.0

    lang = _LANG_MAP.get(language.lower(), "en")

    if _bert_available and _bert_score_fn is not None:
        try:
            model_type = "bert-base-multilingual-cased" if lang != "en" else None
            _, _, F1 = _bert_score_fn(
                [candidate], [reference],
                lang=lang,
                model_type=model_type,
                verbose=False,
                device=None,   # auto-detect CPU/GPU
            )
            score = float(F1[0].item())
            # Rescale from typical [0.85–1.0] BERTScore range to [0–1] for display
            rescaled = max(0.0, (score - 0.80) / 0.20)
            return round(min(1.0, rescaled), 4)
        except Exception as e:
            logger.warning("[BERTScore] bert_score call failed (%s), using fallback", e)

    return _cosine_fallback(candidate, reference)
