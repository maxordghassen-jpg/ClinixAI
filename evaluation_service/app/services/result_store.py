"""
Evaluation result persistence service.

Stores EvalResult documents in MongoDB collection `evaluation_results`.
Provides CRUD + history + trend aggregation.
"""

import logging
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from bson import ObjectId

from app.db.mongo_client import get_db
from schemas.eval_schemas import EvalResult, EvalSummary, TrendPoint, TrendResponse

logger = logging.getLogger(__name__)

COLLECTION = "evaluation_results"
JSON_RESULTS_PATH = Path(__file__).resolve().parents[2] / "evaluation_results.json"
METRIC_COLLECTIONS = {
    "workflow_metrics": "workflow_metrics",
    "intent_metrics": "intent_metrics",
    "memory_metrics": "memory_metrics",
    "llm_judge_metrics": "llm_judge_metrics",
    "multilingual_metrics": "multilingual_metrics",
    "performance_metrics": "performance_metrics",
}


def _to_doc(result: EvalResult) -> dict:
    """Convert EvalResult to a MongoDB-serialisable document."""
    doc = result.model_dump(exclude={"id"})
    # Serialise JudgeDimension objects inside `dimensions`
    if "dimensions" in doc and doc["dimensions"]:
        doc["dimensions"] = {
            k: v if isinstance(v, dict) else v.model_dump()
            for k, v in doc["dimensions"].items()
        }
    return doc


def _from_doc(doc: dict) -> EvalResult:
    """Convert a MongoDB document back to EvalResult."""
    payload = dict(doc)
    payload["id"] = str(payload.pop("_id", payload.get("id", "")))
    return EvalResult(**payload)


def _to_summary(doc: dict) -> EvalSummary:
    workflow_metrics = doc.get("workflow_metrics") or {}
    llm_metrics = doc.get("llm_judge_metrics") or {}
    return EvalSummary(
        id                        = str(doc.get("_id", doc.get("id", ""))),
        scenario_id               = doc.get("scenario_id"),
        overall_score             = doc.get("overall_score"),
        safety_score              = doc.get("safety_score"),
        hallucination_risk        = doc.get("hallucination_risk"),
        answer_relevancy_judge    = doc.get("answer_relevancy_judge"),
        answer_correctness_judge  = doc.get("answer_correctness_judge"),
        groundedness_score        = doc.get("groundedness_score"),
        workflow_score            = doc.get("workflow_score"),
        workflow_success_rate     = doc.get("workflow_success_rate"),
        task_success_rate         = workflow_metrics.get("overall_task_success_rate"),
        workflow_completion_rate  = workflow_metrics.get("overall_completion_rate"),
        faithfulness              = llm_metrics.get("faithfulness"),
        clinical_utility          = llm_metrics.get("clinical_utility"),
        latency_ms                = doc.get("latency_ms"),
        evaluated_at              = doc.get("evaluated_at", ""),
        model_used                = doc.get("model_used", ""),
        language                  = doc.get("language", "english"),
        role                      = doc.get("role", "patient"),
    )


def _read_json_docs() -> list[dict]:
    if not JSON_RESULTS_PATH.exists():
        return []
    try:
        raw = json.loads(JSON_RESULTS_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("[ResultStore] JSON fallback read failed: %s", exc)
        return []
    if not isinstance(raw, list):
        return []
    return [doc for doc in raw if isinstance(doc, dict)]


def _write_json_docs(docs: list[dict]) -> None:
    JSON_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = JSON_RESULTS_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(docs, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    tmp.replace(JSON_RESULTS_PATH)


def _save_json_result(result: EvalResult) -> str:
    doc = _to_doc(result)
    result_id = result.id or f"json:{uuid4().hex}"
    doc["id"] = result_id
    docs = _read_json_docs()
    docs.append(doc)
    _write_json_docs(docs)
    logger.info("[ResultStore] Saved eval result to JSON fallback: %s", JSON_RESULTS_PATH)
    return result_id


def _filter_json_docs(
    docs: list[dict],
    scenario_id: str | None = None,
    role: str | None = None,
    language: str | None = None,
    model_used: str | None = None,
) -> list[dict]:
    if scenario_id:
        docs = [d for d in docs if d.get("scenario_id") == scenario_id]
    if role:
        docs = [d for d in docs if d.get("role") == role]
    if language:
        docs = [d for d in docs if d.get("language") == language]
    if model_used:
        docs = [d for d in docs if d.get("model_used") == model_used]
    return docs


def _json_list_results(
    limit: int = 50,
    skip: int = 0,
    scenario_id: str | None = None,
    role: str | None = None,
    language: str | None = None,
    model_used: str | None = None,
) -> list[EvalSummary]:
    docs = _filter_json_docs(_read_json_docs(), scenario_id, role, language, model_used)
    docs.sort(key=lambda d: d.get("evaluated_at", ""), reverse=True)
    return [_to_summary(d) for d in docs[skip: skip + limit]]


def _json_get_result(result_id: str) -> EvalResult | None:
    for doc in _read_json_docs():
        if str(doc.get("id", "")) == result_id:
            return _from_doc(doc)
    return None


def _json_delete_result(result_id: str) -> bool:
    docs = _read_json_docs()
    kept = [d for d in docs if str(d.get("id", "")) != result_id]
    if len(kept) == len(docs):
        return False
    _write_json_docs(kept)
    return True


def _trend_response_from_docs(docs: list[dict]) -> TrendResponse:
    points = [
        TrendPoint(
            evaluated_at             = d.get("evaluated_at", ""),
            overall_score            = d.get("overall_score"),
            safety_score             = d.get("safety_score"),
            hallucination_risk       = d.get("hallucination_risk"),
            answer_relevancy_judge   = d.get("answer_relevancy_judge"),
            answer_correctness_judge = d.get("answer_correctness_judge"),
            groundedness_score       = d.get("groundedness_score"),
            workflow_score           = d.get("workflow_score"),
            workflow_success_rate    = d.get("workflow_success_rate"),
            task_success_rate        = (d.get("workflow_metrics") or {}).get("overall_task_success_rate"),
            workflow_completion_rate = (d.get("workflow_metrics") or {}).get("overall_completion_rate"),
            faithfulness             = (d.get("llm_judge_metrics") or {}).get("faithfulness"),
            clinical_utility         = (d.get("llm_judge_metrics") or {}).get("clinical_utility"),
            multilingual_consistency = d.get("multilingual_consistency"),
            latency_ms               = d.get("latency_ms"),
            scenario_id              = d.get("scenario_id"),
        )
        for d in docs
    ]

    def _avg(key: str) -> float | None:
        vals = [getattr(p, key) for p in points if getattr(p, key) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    avgs = {k: v for k, v in {
        "overall_score":             _avg("overall_score"),
        "safety_score":              _avg("safety_score"),
        "hallucination_risk":        _avg("hallucination_risk"),
        "answer_relevancy_judge":    _avg("answer_relevancy_judge"),
        "answer_correctness_judge":  _avg("answer_correctness_judge"),
        "groundedness_score":        _avg("groundedness_score"),
        "workflow_score":            _avg("workflow_score"),
        "workflow_success_rate":     _avg("workflow_success_rate"),
        "task_success_rate":         _avg("task_success_rate"),
        "workflow_completion_rate":  _avg("workflow_completion_rate"),
        "faithfulness":              _avg("faithfulness"),
        "clinical_utility":          _avg("clinical_utility"),
        "multilingual_consistency":  _avg("multilingual_consistency"),
        "latency_ms":                _avg("latency_ms"),
    }.items() if v is not None}

    scored = [d for d in docs if d.get("overall_score") is not None]
    best = _to_summary(max(scored, key=lambda d: d.get("overall_score"))) if scored else None
    worst = _to_summary(min(scored, key=lambda d: d.get("overall_score"))) if scored else None
    return TrendResponse(points=points, averages=avgs, best_run=best, worst_run=worst)


# ── Write ─────────────────────────────────────────────────────────────────────

async def save_result(result: EvalResult) -> str:
    """Persist a result and return its id. Falls back to JSON if MongoDB is unavailable."""
    try:
        db  = get_db()
        doc = _to_doc(result)
        res = await db[COLLECTION].insert_one(doc)
        result_id = str(res.inserted_id)
        evaluated_at = doc.get("evaluated_at")
        for field, collection in METRIC_COLLECTIONS.items():
            payload = doc.get(field) or {}
            await db[collection].insert_one({
                "result_id": result_id,
                "scenario_id": doc.get("scenario_id"),
                "evaluated_at": evaluated_at,
                "metrics": payload,
            })
        logger.debug("[ResultStore] Saved eval result %s", res.inserted_id)
        return result_id
    except Exception as exc:
        logger.warning("[ResultStore] MongoDB unavailable; using JSON fallback: %s", exc)
        return _save_json_result(result)


# ── Read ──────────────────────────────────────────────────────────────────────

async def get_result(result_id: str) -> EvalResult | None:
    try:
        db  = get_db()
        doc = await db[COLLECTION].find_one({"_id": ObjectId(result_id)})
        if doc:
            return _from_doc(doc)
    except Exception:
        pass
    return _json_get_result(result_id)


async def list_results(
    limit: int = 50,
    skip:  int = 0,
    scenario_id: str | None = None,
    role:        str | None = None,
    language:    str | None = None,
    model_used:  str | None = None,
) -> list[EvalSummary]:
    filt: dict[str, Any] = {}
    if scenario_id: filt["scenario_id"] = scenario_id
    if role:        filt["role"]        = role
    if language:    filt["language"]    = language
    if model_used:  filt["model_used"]  = model_used

    try:
        db = get_db()
        cursor = (
            db[COLLECTION]
            .find(filt, {
                "_id": 1, "scenario_id": 1, "overall_score": 1,
                "safety_score": 1, "hallucination_risk": 1,
                "answer_relevancy_judge": 1, "answer_correctness_judge": 1,
                "groundedness_score": 1, "workflow_score": 1,
                "workflow_success_rate": 1,
                "workflow_metrics": 1, "llm_judge_metrics": 1,
                "latency_ms": 1, "evaluated_at": 1, "model_used": 1,
                "language": 1, "role": 1,
            })
            .sort("evaluated_at", -1)
            .skip(skip)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        return [_to_summary(d) for d in docs]
    except Exception as exc:
        logger.warning("[ResultStore] MongoDB list failed; using JSON fallback: %s", exc)
        return _json_list_results(limit, skip, scenario_id, role, language, model_used)


async def get_history(limit: int = 100) -> list[EvalSummary]:
    return await list_results(limit=limit)


async def get_trends(
    limit: int = 200,
    scenario_id: str | None = None,
) -> TrendResponse:
    filt: dict[str, Any] = {}
    if scenario_id:
        filt["scenario_id"] = scenario_id

    try:
        db = get_db()
        cursor = (
            db[COLLECTION]
            .find(filt, {
                "_id": 1, "evaluated_at": 1, "overall_score": 1,
                "safety_score": 1, "hallucination_risk": 1,
                "answer_relevancy_judge": 1, "answer_correctness_judge": 1,
                "groundedness_score": 1,
                "workflow_score": 1, "workflow_success_rate": 1,
                "multilingual_consistency": 1,
                "workflow_metrics": 1, "llm_judge_metrics": 1,
                "latency_ms": 1, "scenario_id": 1,
            })
            .sort("evaluated_at", 1)
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
    except Exception as exc:
        logger.warning("[ResultStore] MongoDB trends failed; using JSON fallback: %s", exc)
        docs = _filter_json_docs(_read_json_docs(), scenario_id=scenario_id)
        docs.sort(key=lambda d: d.get("evaluated_at", ""))
        docs = docs[:limit]
    return _trend_response_from_docs(docs)


async def delete_result(result_id: str) -> bool:
    try:
        db = get_db()
        res = await db[COLLECTION].delete_one({"_id": ObjectId(result_id)})
        if res.deleted_count == 1:
            return True
    except Exception:
        pass
    return _json_delete_result(result_id)
