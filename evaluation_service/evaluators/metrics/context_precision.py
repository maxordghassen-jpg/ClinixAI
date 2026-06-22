"""
Context Precision metric.

Measures how precisely the retrieved memory context is used in the response.

Formula:
  - For each retrieved memory snippet, compute cosine similarity to response.
  - Precision = fraction of retrieved memories that are semantically reflected
    in the response (similarity ≥ threshold).
  - If no memories were retrieved, returns 0.5 (neutral).

Uses paraphrase-multilingual-MiniLM-L12-v2 for EN/FR/AR.
"""

import logging

logger = logging.getLogger(__name__)

_PRECISION_THRESHOLD = 0.40
_st_model = None


def _load_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            logger.warning("[ContextPrecision] sentence-transformers unavailable: %s", e)
    return _st_model


def compute_context_precision(
    agent_response: str,
    retrieved_memories: list[str],
    threshold: float = _PRECISION_THRESHOLD,
) -> float:
    """
    Returns fraction of retrieved memories reflected in the agent response.
    Returns 0.5 when no memories were retrieved (not evaluable — neutral).
    Returns float ∈ [0, 1].
    """
    if not retrieved_memories:
        return 0.5   # neutral — context precision not applicable
    if not agent_response:
        return 0.0

    import numpy as np
    model = _load_model()
    if model is None:
        return 0.5

    try:
        texts = [agent_response] + retrieved_memories
        embs  = model.encode(texts, show_progress_bar=False)
        norm  = lambda v: v / (float(np.linalg.norm(v)) + 1e-9)
        resp_vec = norm(embs[0])

        hits = sum(
            1 for mem_emb in embs[1:]
            if float(np.dot(resp_vec, norm(mem_emb))) >= threshold
        )
        return round(hits / len(retrieved_memories), 4)
    except Exception as e:
        logger.warning("[ContextPrecision] Failed: %s", e)
        return 0.5
