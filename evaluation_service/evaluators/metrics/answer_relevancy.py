"""
Answer Relevancy metric.

Measures how well the agent response addresses the user question.
Uses cosine similarity between:
  - The user question embedding
  - The agent response embedding

High relevancy = response is semantically close to what was asked.
A correct but off-topic answer scores lower than a concise on-topic one.

Uses paraphrase-multilingual-MiniLM-L12-v2 for EN/FR/AR support.
"""

import logging

logger = logging.getLogger(__name__)

_st_model = None


def _load_model():
    global _st_model
    if _st_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _st_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        except Exception as e:
            logger.warning("[AnswerRelevancy] sentence-transformers unavailable: %s", e)
    return _st_model


def compute_answer_relevancy(user_message: str, agent_response: str) -> float:
    """
    Cosine similarity between user question and agent response ∈ [0, 1].
    Does NOT require a reference answer — measures question–answer alignment.
    """
    if not user_message or not agent_response:
        return 0.0
    import numpy as np
    model = _load_model()
    if model is None:
        return 0.5
    try:
        embs = model.encode([user_message, agent_response], show_progress_bar=False)
        norm = lambda v: v / (float(np.linalg.norm(v)) + 1e-9)
        score = float(np.dot(norm(embs[0]), norm(embs[1])))
        return round(max(0.0, min(1.0, score)), 4)
    except Exception as e:
        logger.warning("[AnswerRelevancy] Failed: %s", e)
        return 0.5
