"""
Evaluation service API routes.

Endpoints:
  GET  /health
  GET  /scenarios
  GET  /scenarios/{id}
  POST /evaluate              — single evaluation
  POST /evaluate/batch        — batch evaluation
  POST /evaluate/multilingual — cross-language consistency
  POST /run/{scenario_id}     — end-to-end scenario runner

  GET  /results               — list stored results (filterable)
  GET  /results/history       — full history (100 most recent)
  GET  /results/trends        — trend data for charts
  GET  /results/{id}          — fetch one result by MongoDB id
  DELETE /results/{id}        — delete a result
  POST /results/compare       — compare two runs side-by-side

  GET  /results/export/csv    — CSV export
  GET  /results/export/json   — JSON export
"""

import csv
import io
import json
import logging
import uuid
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.config.settings import settings
from datasets.eval_scenarios import SCENARIO_INDEX, SCENARIOS
from evaluators.judge.llm_judge import LLMJudge
from evaluators.orchestrator import run_evaluation, run_batch
from evaluators.framework_metrics import aggregate_framework_results
from schemas.eval_schemas import (
    BatchEvalRequest,
    BatchEvalResult,
    CompareRequest,
    CompareResult,
    EvalRequest,
    EvalResult,
    EvalScenario,
    EvalSummary,
    MultilingualEvalRequest,
    TrendResponse,
    WorkflowContext,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["evaluation"])
_judge = LLMJudge()


def _as_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        if isinstance(item, str):
            out.append(item)
        elif isinstance(item, dict):
            text = item.get("text") or item.get("content") or item.get("summary") or item.get("value")
            if text:
                out.append(str(text))
    return out


def _memory_source_lists(data: dict[str, Any]) -> dict[str, list[str]]:
    sources = data.get("retrieved_memory_sources") or data.get("memory_sources") or {}
    if not isinstance(sources, dict):
        sources = {}
    return {
        "Redis": _as_text_list(sources.get("Redis") or sources.get("redis") or []),
        "MongoDB": _as_text_list(sources.get("MongoDB") or sources.get("mongodb") or sources.get("mongo") or []),
        "Semantic Memory": _as_text_list(
            sources.get("Semantic Memory") or sources.get("semantic") or sources.get("semantic_memory") or []
        ),
    }


def _mongo_enabled() -> bool:
    return settings.ENABLE_MONGO


async def _persist(result: EvalResult) -> EvalResult:
    """Save result using MongoDB when available, otherwise JSON fallback."""
    try:
        from app.services.result_store import save_result
        result_id   = await save_result(result)
        result.id   = result_id
    except Exception as e:
        logger.warning("[Routes] Result persistence failed: %s", e)
    return result


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {
        "status":      "ok",
        "service":     "ClinixAI Evaluation Service",
        "version":     "2.0.0",
        "judge_model": settings.JUDGE_MODEL,
        "mongo":       _mongo_enabled(),
    }


# ── Scenario catalogue ────────────────────────────────────────────────────────

@router.get("/scenarios", response_model=list[EvalScenario])
async def list_scenarios(
    category: Annotated[str | None, Query()] = None,
    role:     Annotated[str | None, Query()] = None,
    language: Annotated[str | None, Query()] = None,
):
    results = SCENARIOS
    if category: results = [s for s in results if s.category == category]
    if role:     results = [s for s in results if s.role     == role]
    if language: results = [s for s in results if s.language == language]

    # Guard: skip any scenario that fails serialization rather than 500-ing
    safe = []
    for s in results:
        try:
            s.model_dump()
            safe.append(s)
        except Exception as exc:
            logger.warning("/scenarios: skipping scenario %r — serialization error: %s", s.id, exc)
    return safe


@router.get("/scenarios/{scenario_id}", response_model=EvalScenario)
async def get_scenario(scenario_id: str):
    scenario = SCENARIO_INDEX.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    return scenario


# ── Core evaluation ───────────────────────────────────────────────────────────

@router.post("/evaluate", response_model=EvalResult)
async def evaluate(req: EvalRequest):
    result = await run_evaluation(req)
    return await _persist(result)


@router.post("/evaluate/batch", response_model=BatchEvalResult)
async def evaluate_batch(req: BatchEvalRequest):
    if len(req.requests) > 50:
        raise HTTPException(status_code=400, detail="Batch size limited to 50 requests.")
    results, aggregate = await run_batch(req.requests)
    for r in results:
        await _persist(r)
    return BatchEvalResult(results=results, aggregate=aggregate)


@router.post("/evaluate/multilingual", response_model=EvalResult)
async def evaluate_multilingual(req: MultilingualEvalRequest):
    from datetime import datetime, timezone
    dimension = await _judge.evaluate_multilingual(req)
    result = EvalResult(
        multilingual_consistency = dimension.score,
        dimensions               = {"multilingual_consistency": dimension},
        overall_score            = dimension.score,
        judge_explanation        = dimension.explanation,
        evaluated_at             = datetime.now(timezone.utc).isoformat(),
        model_used               = settings.JUDGE_MODEL,
    )
    return await _persist(result)


# ── Scenario runner ───────────────────────────────────────────────────────────

@router.post("/run/{scenario_id}", response_model=EvalResult)
async def run_scenario(scenario_id: str):
    """
    End-to-end: load scenario → call live agent → evaluate → persist → return.
    """
    scenario = SCENARIO_INDEX.get(scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")

    endpoint = (
        f"{settings.AGENT_SERVICE_URL}/doctor/chat"
        if scenario.role == "doctor"
        else f"{settings.AGENT_SERVICE_URL}/patient/chat"
    )
    eval_session_id = f"eval:{uuid.uuid4().hex[:12]}"

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(endpoint, json={
                "message":    scenario.user_message,
                "session_id": eval_session_id,
            })
            resp.raise_for_status()
            data = resp.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Agent service unreachable at {settings.AGENT_SERVICE_URL}.",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail=f"Agent service returned {e.response.status_code}.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent service error: {e}")

    agent_response     = data.get("response", "")
    memory_data = data.get("memory", {})
    if not isinstance(memory_data, dict):
        memory_data = {}
    retrieved_memories = _as_text_list(data.get("retrieved_memories"))
    retrieved_memory_sources = _memory_source_lists(data)
    predicted_intent = memory_data.get("intent") or data.get("detected_intent")
    recommended_specialty = memory_data.get("recommended_specialty")

    actual_transition_sequence = data.get("actual_transition_sequence") or data.get("transition_sequence")
    if not isinstance(actual_transition_sequence, list):
        actual_transition_sequence = None
    trace_unavailable = actual_transition_sequence is None

    workflow_ctx = None
    if scenario.expected_tool or scenario.expected_workflow:
        workflow_ctx = WorkflowContext(
            expected_tool   = scenario.expected_tool,
            expected_action = scenario.expected_workflow,
            workflow_state  = {
                "actual_memory_step": memory_data.get("step"),
                "actual_intent": predicted_intent,
            },
            ui_action       = data.get("ui_action"),
            actual_transition_sequence = actual_transition_sequence,
            trace_unavailable = trace_unavailable,
        )

    has_ref = bool(scenario.reference_response)
    eval_req = EvalRequest(
        scenario_id        = scenario.id,
        user_message       = scenario.user_message,
        agent_response     = agent_response,
        reference_response = scenario.reference_response,
        language           = scenario.language,
        role               = scenario.role,
        workflow           = workflow_ctx,
        retrieved_memories = retrieved_memories,
        retrieved_memory_sources = retrieved_memory_sources,
        predicted_intent    = str(predicted_intent) if predicted_intent else None,
        recommended_specialty = str(recommended_specialty) if recommended_specialty else None,
        context            = scenario.context,
        # Disabled metric toggles — kept in schema but not computed
        include_bert_score        = False,
        include_rouge             = False,
        include_bleu              = False,
        include_em                = False,
        include_esm               = False,
        include_answer_metrics    = False,
        include_context_precision = False,
    )

    result = await run_evaluation(eval_req)

    # workflow_success_rate: override with scenario expectation when a
    # workflow context was provided and the judge scored it.
    if scenario.expected_workflow_success and workflow_ctx:
        ws = result.workflow_score
        result.workflow_success_rate = 1.0 if (ws is not None and ws >= 0.70) else 0.0
    elif workflow_ctx and result.workflow_score is not None:
        result.workflow_success_rate = 1.0 if result.workflow_score >= 0.70 else 0.0

    return await _persist(result)


# ── Result history ────────────────────────────────────────────────────────────

@router.get("/results", response_model=list[EvalSummary])
async def list_eval_results(
    limit:       Annotated[int, Query(ge=1, le=200)] = 50,
    skip:        Annotated[int, Query(ge=0)]         = 0,
    scenario_id: Annotated[str | None, Query()]      = None,
    role:        Annotated[str | None, Query()]      = None,
    language:    Annotated[str | None, Query()]      = None,
    model_used:  Annotated[str | None, Query()]      = None,
):
    from app.services.result_store import list_results
    return await list_results(limit, skip, scenario_id, role, language, model_used)


@router.get("/results/history", response_model=list[EvalSummary])
async def get_eval_history(
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
):
    from app.services.result_store import get_history
    return await get_history(limit)


@router.get("/results/trends", response_model=TrendResponse)
async def get_eval_trends(
    limit:       Annotated[int, Query(ge=1, le=500)] = 200,
    scenario_id: Annotated[str | None, Query()]      = None,
):
    from app.services.result_store import get_trends
    return await get_trends(limit, scenario_id)


@router.get("/results/framework")
async def get_framework_results(
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
):
    from app.services.result_store import list_results, get_result

    summaries = await list_results(limit=limit)
    results = []
    for summary in summaries:
        result = await get_result(summary.id)
        if result:
            results.append(result)
    return aggregate_framework_results(results)


@router.get("/results/{result_id}", response_model=EvalResult)
async def get_eval_result(result_id: str):
    from app.services.result_store import get_result
    result = await get_result(result_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found.")
    return result


@router.delete("/results/{result_id}")
async def delete_eval_result(result_id: str):
    from app.services.result_store import delete_result
    ok = await delete_result(result_id)
    if not ok:
        raise HTTPException(status_code=404, detail=f"Result '{result_id}' not found.")
    return {"deleted": result_id}


@router.post("/results/compare", response_model=CompareResult)
async def compare_eval_results(req: CompareRequest):
    from app.services.result_store import get_result
    run_a = await get_result(req.id_a)
    run_b = await get_result(req.id_b)
    if not run_a:
        raise HTTPException(status_code=404, detail=f"Result '{req.id_a}' not found.")
    if not run_b:
        raise HTTPException(status_code=404, detail=f"Result '{req.id_b}' not found.")

    numeric_fields = [
        "overall_score", "safety_score", "hallucination_risk",
        "groundedness_score", "workflow_success_rate",
        "conversational_quality", "latency_ms",
    ]
    delta: dict[str, float | None] = {}
    for f in numeric_fields:
        a = getattr(run_a, f)
        b = getattr(run_b, f)
        if a is not None and b is not None:
            delta[f] = round(b - a, 4)
        else:
            delta[f] = None

    return CompareResult(run_a=run_a, run_b=run_b, delta=delta)


# ── Export ────────────────────────────────────────────────────────────────────

@router.get("/results/export/json")
async def export_json(
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    scenario_id: Annotated[str | None, Query()] = None,
):
    from app.services.result_store import list_results
    rows = await list_results(limit=limit, scenario_id=scenario_id)
    payload = json.dumps([r.model_dump() for r in rows], indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(payload.encode()),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=eval_results.json"},
    )


@router.get("/results/export/csv")
async def export_csv(
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    scenario_id: Annotated[str | None, Query()] = None,
):
    from app.services.result_store import list_results
    rows = await list_results(limit=limit, scenario_id=scenario_id)

    buf = io.StringIO()
    fieldnames = [
        "id", "scenario_id",
        "overall_score",
        "safety_score", "hallucination_risk",
        "groundedness_score", "workflow_success_rate",
        "task_success_rate", "workflow_completion_rate",
        "faithfulness", "clinical_utility",
        "latency_ms", "evaluated_at", "model_used", "language", "role",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for r in rows:
        writer.writerow(r.model_dump())

    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=eval_results.csv"},
    )
