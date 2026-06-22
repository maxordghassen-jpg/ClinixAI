"""
ROUGE score evaluation with text normalization and multi-reference support.

Use for: summary quality, appointment confirmation overlap.
Do NOT use for workflow or intent evaluation (surface overlap only).

Install: pip install rouge-score
"""

import logging
from dataclasses import dataclass

from evaluators.metrics.text_normalizer import normalize_multi

logger = logging.getLogger(__name__)

_rouge_available = False
_scorer_cache: dict = {}

try:
    from rouge_score import rouge_scorer  # type: ignore
    _rouge_available = True
    logger.info("[ROUGE] rouge_score package available")
except ImportError:
    logger.warning("[ROUGE] rouge_score not installed — all ROUGE scores will be 0.0. "
                   "Install: pip install rouge-score")


@dataclass
class RougeScores:
    rouge1: float
    rouge2: float
    rougeL: float


def _get_scorer():
    if not _rouge_available:
        return None
    key = "all"
    if key not in _scorer_cache:
        from rouge_score import rouge_scorer as rs
        # use_stemmer=True helps with English plurals/conjugations.
        # For multilingual text the stemmer is a no-op — acceptable.
        _scorer_cache[key] = rs.RougeScorer(
            ["rouge1", "rouge2", "rougeL"],
            use_stemmer=True,
        )
    return _scorer_cache[key]


def _score_pair(norm_candidate: str, norm_reference: str) -> RougeScores:
    scorer = _get_scorer()
    if scorer is None:
        return RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)
    scores = scorer.score(norm_reference, norm_candidate)
    return RougeScores(
        rouge1=round(float(scores["rouge1"].fmeasure), 4),
        rouge2=round(float(scores["rouge2"].fmeasure), 4),
        rougeL=round(float(scores["rougeL"].fmeasure), 4),
    )


def compute_rouge_scores(
    candidate: str,
    reference: str,
    extra_references: list[str] | None = None,
) -> RougeScores:
    """
    Compute ROUGE-1/2/L F1.

    Text normalization is applied before scoring to eliminate zero-scores
    from punctuation, casing, apostrophes, and bullet-point formatting.

    When extra_references is provided, returns the BEST score across all
    references (multi-reference evaluation).
    """
    if not _rouge_available:
        logger.warning("[ROUGE] rouge_score not installed — returning zeros")
        return RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)
    if not candidate or not reference:
        logger.debug("[ROUGE] Empty candidate or reference — returning zeros")
        return RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)

    try:
        all_references = [reference] + (extra_references or [])
        norm_candidate, norm_refs = normalize_multi(candidate, all_references)

        if not norm_candidate:
            logger.debug("[ROUGE] Candidate is empty after normalization")
            return RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)

        best = RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)
        for norm_ref in norm_refs:
            if not norm_ref:
                continue
            s = _score_pair(norm_candidate, norm_ref)
            logger.debug(
                "[ROUGE] cand=%.40r ref=%.40r R1=%.3f R2=%.3f RL=%.3f",
                norm_candidate, norm_ref, s.rouge1, s.rouge2, s.rougeL,
            )
            if s.rouge1 > best.rouge1:
                best = s

        logger.debug("[ROUGE] Best scores: R1=%.3f R2=%.3f RL=%.3f",
                     best.rouge1, best.rouge2, best.rougeL)
        return best

    except Exception as exc:
        logger.warning("[ROUGE] Computation failed: %s", exc)
        return RougeScores(rouge1=0.0, rouge2=0.0, rougeL=0.0)


def compute_rouge_score(
    candidate: str,
    reference: str,
    metric: str = "rougeL",
) -> float:
    """Single-metric accessor for backwards compatibility."""
    return getattr(compute_rouge_scores(candidate, reference), metric, 0.0)
