"""
BLEU score evaluation with text normalization and multi-reference support.

Use for: translation quality, multilingual surface comparison.
Do NOT use for workflow correctness — BLEU punishes valid paraphrases.

Install: pip install sacrebleu
"""

import logging

from evaluators.metrics.text_normalizer import normalize_multi

logger = logging.getLogger(__name__)

_sacrebleu_available = False

try:
    import sacrebleu  # type: ignore
    _sacrebleu_available = True
    logger.info("[BLEU] sacrebleu package available")
except ImportError:
    logger.warning("[BLEU] sacrebleu not installed — all BLEU scores will be 0.0. "
                   "Install: pip install sacrebleu")


def compute_bleu_score(
    candidate: str,
    reference: str,
    extra_references: list[str] | None = None,
) -> float:
    """
    sentence-BLEU normalised to [0, 1] from sacrebleu's [0, 100] range.

    Text normalization is applied before scoring.
    When extra_references is provided, BLEU is computed against all references
    simultaneously (sacrebleu natively supports multi-reference BLEU).
    """
    if not _sacrebleu_available:
        logger.warning("[BLEU] sacrebleu not installed — returning 0.0")
        return 0.0
    if not candidate or not reference:
        logger.debug("[BLEU] Empty candidate or reference — returning 0.0")
        return 0.0

    try:
        all_references = [reference] + (extra_references or [])
        norm_candidate, norm_refs = normalize_multi(candidate, all_references)

        if not norm_candidate or not any(norm_refs):
            logger.debug("[BLEU] Empty after normalization")
            return 0.0

        result = sacrebleu.sentence_bleu(norm_candidate, norm_refs)  # type: ignore
        score = round(min(1.0, result.score / 100.0), 4)
        logger.debug("[BLEU] cand=%.40r score=%.3f", norm_candidate, score)
        return score

    except Exception as exc:
        logger.warning("[BLEU] Computation failed: %s", exc)
        return 0.0
