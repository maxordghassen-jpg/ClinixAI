"""
Evaluation orchestrator for the ClinixAI thesis framework.

Each run now emits six metric groups:
  - workflow_metrics
  - intent_metrics
  - memory_metrics
  - llm_judge_metrics
  - multilingual_metrics
  - performance_metrics
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from app.config.settings import settings
from datasets.eval_scenarios import SCENARIO_INDEX
from evaluators.framework_metrics import (
    compute_intent_metrics,
    compute_llm_judge_metrics,
    compute_memory_metrics,
    compute_multilingual_metrics,
    compute_performance_metrics,
    compute_workflow_metrics,
)
from evaluators.judge.llm_judge import LLMJudge
from schemas.eval_schemas import EvalRequest, EvalResult, JudgeDimension

logger = logging.getLogger(__name__)

_judge = LLMJudge()

_OVERALL_KEYS = [
    "completeness",
    "accuracy",
    "faithfulness",
    "safety_score",
    "clinical_utility",
    "conversation_quality",
]


def _score(dimensions: dict[str, JudgeDimension], key: str) -> float | None:
    return dimensions[key].score if key in dimensions else None


def _overall(llm_metrics: dict[str, float]) -> float | None:
    vals = [llm_metrics[k] for k in _OVERALL_KEYS if k in llm_metrics and llm_metrics[k] is not None]
    if not vals:
        return None
    return round((sum(vals) / len(vals)) / 5.0, 4)


async def run_evaluation(req: EvalRequest) -> EvalResult:
    t_start = time.monotonic()

    dimensions: dict[str, JudgeDimension] = {}
    try:
        dimensions = await _judge.evaluate(req)
    except Exception as exc:
        logger.error("[Orchestrator] LLM judge failed: %s", exc)

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    scenario = SCENARIO_INDEX.get(req.scenario_id or "")

    workflow_metrics = compute_workflow_metrics(req, dimensions, scenario)
    intent_metrics = compute_intent_metrics(req, scenario)
    memory_metrics = compute_memory_metrics(req, dimensions, scenario)
    llm_judge_metrics = compute_llm_judge_metrics(dimensions)
    multilingual_metrics = compute_multilingual_metrics(req, dimensions)
    performance_metrics = compute_performance_metrics(latency_ms, req.token_usage)

    hallucination_risk = (
        round(1.0 - dimensions["hallucination"].score, 4)
        if "hallucination" in dimensions else None
    )
    workflow_success_rate = (
        workflow_metrics.get("overall_task_success_rate", 0.0) / 100.0
        if req.workflow else None
    )

    result = EvalResult(
        scenario_id=req.scenario_id,

        # Compatibility aliases for existing consumers.
        safety_score=_score(dimensions, "safety"),
        hallucination_risk=hallucination_risk,
        groundedness_score=_score(dimensions, "faithfulness") or _score(dimensions, "groundedness"),
        workflow_score=_score(dimensions, "workflow"),
        workflow_success_rate=workflow_success_rate,
        conversational_quality=_score(dimensions, "conversation_quality"),
        answer_relevancy_judge=None,
        answer_correctness_judge=None,
        context_precision_judge=None,
        multilingual_consistency=_score(dimensions, "multilingual_consistency"),

        dimensions=dimensions,
        overall_score=_overall(llm_judge_metrics),
        workflow_metrics=workflow_metrics,
        intent_metrics=intent_metrics,
        memory_metrics=memory_metrics,
        llm_judge_metrics=llm_judge_metrics,
        multilingual_metrics=multilingual_metrics,
        performance_metrics=performance_metrics,

        judge_explanation="; ".join(
            f"{k}: {v.explanation}" for k, v in dimensions.items()
        )[:1500],
        latency_ms=latency_ms,
        evaluated_at=datetime.now(timezone.utc).isoformat(),
        model_used=settings.JUDGE_MODEL,
        user_message=req.user_message,
        agent_response=req.agent_response,
        reference_response=req.reference_response,
        language=req.language,
        role=req.role,
        tags=scenario.tags if scenario else [],
    )
    return result


async def run_batch(requests: list[EvalRequest]) -> tuple[list[EvalResult], dict[str, float]]:
    results = await asyncio.gather(
        *[run_evaluation(req) for req in requests],
        return_exceptions=True,
    )

    eval_results: list[EvalResult] = []
    for i, result in enumerate(results):
        if isinstance(result, BaseException):
            logger.warning("[Orchestrator] Batch item %d failed: %s", i, result)
        else:
            eval_results.append(result)

    aggregate: dict[str, float] = {}
    keys = [
        "overall_score",
        "safety_score",
        "hallucination_risk",
        "groundedness_score",
        "workflow_success_rate",
        "latency_ms",
    ]
    for key in keys:
        vals = [getattr(r, key) for r in eval_results if getattr(r, key) is not None]
        if vals:
            aggregate[key] = round(sum(vals) / len(vals), 4)
    return eval_results, aggregate
