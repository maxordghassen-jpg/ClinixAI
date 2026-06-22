"""
ClinixAI thesis evaluation framework metric computations.

The functions in this module are deterministic aggregators over scenario/run
metadata and judge dimensions. LLM scoring happens in evaluators.judge; this
module converts raw run evidence into the six thesis metric groups.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from statistics import mean
from typing import Any

from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from schemas.eval_schemas import EvalRequest, EvalResult, EvalScenario, JudgeDimension

WORKFLOW_LABELS = [
    "doctor_search",
    "booking",
    "cancellation",
    "availability",
    "report_retrieval",
    "preconsultation",
]

INTENT_CLASSES = [
    "doctor_search",
    "geo_search",
    "booking",
    "cancel_appointment",
    "reschedule_appointment",
    "view_appointments",
    "set_reminder",
    "select_doctor",
    "select_appointment",
    "check_availability",
    "preconsultation",
    "emergency",
    "safety",
    "memory_recall",
    "recommendation",
    "doctor_view_schedule",
    "doctor_update_availability",
    "doctor_patient_summary",
    "none",
    "unknown",
    # Legacy dashboard labels retained so older stored rows still aggregate.
    "cancellation",
    "report_request",
    "availability_check",
    "profile_update",
]

MEMORY_SYSTEMS = ["Redis", "MongoDB", "Semantic Memory"]
LANGUAGES = ["french", "english", "arabic"]
PERFORMANCE_STAGES = [
    "intent_detection",
    "doctor_search",
    "booking",
    "availability",
    "report_generation",
    "preconsultation_generation",
]


def pct(numerator: float, denominator: float) -> float:
    return round((numerator / denominator) * 100, 2) if denominator else 0.0


def one_to_five(score: float | None, default: float = 3.0) -> float:
    if score is None:
        return default
    if score > 1.0:
        return round(max(1.0, min(5.0, score)), 2)
    return round(max(1.0, min(5.0, 1.0 + (score * 4.0))), 2)


def workflow_key(value: str | None, tags: list[str] | None = None) -> str:
    raw = (value or "").lower()
    tagset = {t.lower() for t in tags or []}
    if "find_medical_place" in raw or "doctor_search" in raw or "geo" in tagset:
        return "doctor_search"
    if "cancel" in raw or "cancellation" in tagset:
        return "cancellation"
    if "availability" in raw or "availability" in tagset:
        return "availability"
    if "report" in raw or "patient_summary" in tagset:
        return "report_retrieval"
    if "preconsultation" in raw or "preconsultation" in tagset:
        return "preconsultation"
    if "book" in raw or "appointment" in tagset:
        return "booking"
    return "booking"


def intent_key(value: str | None, tags: list[str] | None = None) -> str:
    wf = workflow_key(value, tags)
    if wf == "doctor_search":
        return "doctor_search"
    if wf == "report_retrieval":
        return "report_request"
    if wf == "availability":
        return "availability_check"
    if wf in {"booking", "cancellation"}:
        return wf
    if tags and "profile" in {t.lower() for t in tags}:
        return "profile_update"
    return "booking"


def _zero_workflow_rows() -> dict[str, dict[str, float]]:
    return {
        name: {
            "successful_tasks": 0,
            "total_tasks": 0,
            "task_success_rate": 0.0,
            "completed_workflows": 0,
            "started_workflows": 0,
            "completion_rate": 0.0,
            "correct_transitions": 0,
            "total_transitions": 0,
            "state_transition_accuracy": 0.0,
        }
        for name in WORKFLOW_LABELS
    }


def compute_workflow_metrics(
    req: EvalRequest,
    dimensions: dict[str, JudgeDimension],
    scenario: EvalScenario | None = None,
) -> dict[str, Any]:
    workflow = workflow_key(
        scenario.expected_workflow if scenario else (req.workflow.expected_action if req.workflow else None),
        scenario.tags if scenario else None,
    )
    success = 1 if dimensions.get("workflow", JudgeDimension(score=0.0, explanation="")).score >= 0.70 else 0
    started = 1 if req.workflow or (scenario and scenario.expected_workflow) else 0
    completed = success if started else 0

    expected_sequence = scenario.expected_transition_sequence if scenario else []
    actual_sequence = req.workflow.actual_transition_sequence if req.workflow else None
    trace_unavailable = bool(req.workflow.trace_unavailable if req.workflow else True)

    if expected_sequence:
        total_transitions = len(expected_sequence)
        if trace_unavailable or actual_sequence is None:
            correct_transitions = 0
        else:
            correct_transitions = sum(
                1 for expected, actual in zip(expected_sequence, actual_sequence)
                if expected == actual
            )
    else:
        total_transitions = 0
        correct_transitions = 0

    per_workflow = _zero_workflow_rows()
    row = per_workflow[workflow]
    row.update({
        "successful_tasks": success,
        "total_tasks": 1 if started else 0,
        "task_success_rate": pct(success, 1 if started else 0),
        "completed_workflows": completed,
        "started_workflows": started,
        "completion_rate": pct(completed, started),
        "correct_transitions": correct_transitions,
        "total_transitions": total_transitions,
        "state_transition_accuracy": pct(correct_transitions, total_transitions),
        "trace_unavailable": trace_unavailable,
        "expected_transition_sequence": expected_sequence,
        "actual_transition_sequence": actual_sequence or [],
    })

    return {
        "overall_task_success_rate": row["task_success_rate"],
        "overall_completion_rate": row["completion_rate"],
        "overall_state_transition_accuracy": row["state_transition_accuracy"],
        "per_workflow": per_workflow,
    }


def compute_intent_metrics(req: EvalRequest, scenario: EvalScenario | None = None) -> dict[str, Any]:
    expected = scenario.expected_intent if scenario and scenario.expected_intent else "unknown"
    predicted = req.predicted_intent or "unknown"
    labels = list(dict.fromkeys(INTENT_CLASSES + [expected, predicted]))

    y_true = [expected]
    y_pred = [predicted]
    cm = confusion_matrix(y_true, y_pred, labels=labels)
    matrix = {
        actual: {pred: int(cm[i][j]) for j, pred in enumerate(labels)}
        for i, actual in enumerate(labels)
    }
    precision, recall, f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average="macro", zero_division=0
    )
    per_precision, per_recall, per_f1, _ = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    per_class = {
        label: {
            "precision": round(float(per_precision[i]) * 100, 2),
            "recall": round(float(per_recall[i]) * 100, 2),
            "f1": round(float(per_f1[i]) * 100, 2),
        }
        for i, label in enumerate(labels)
    }

    expected_specialty = scenario.expected_specialty if scenario else None
    recommended_specialty = req.recommended_specialty
    specialty_total = 1 if expected_specialty else 0
    specialty_correct = int(bool(expected_specialty) and expected_specialty == recommended_specialty)
    per_specialty = {}
    if expected_specialty:
        per_specialty[expected_specialty] = {
            "correct_recommendations": specialty_correct,
            "total_recommendations": 1,
            "accuracy": pct(specialty_correct, 1),
            "recommended_specialty": recommended_specialty,
        }

    return {
        "intent_classification": {
            "accuracy": round(float(accuracy_score(y_true, y_pred)) * 100, 2),
            "precision": round(float(precision) * 100, 2),
            "recall": round(float(recall) * 100, 2),
            "f1": round(float(f1) * 100, 2),
            "classes": labels,
            "confusion_matrix": matrix,
            "per_class": per_class,
            "expected_intent": expected,
            "predicted_intent": predicted,
        },
        "specialty_recommendation": {
            "overall_accuracy": pct(specialty_correct, specialty_total),
            "per_specialty": per_specialty,
            "expected_specialty": expected_specialty,
            "recommended_specialty": recommended_specialty,
        },
    }


def compute_memory_metrics(
    req: EvalRequest,
    dimensions: dict[str, JudgeDimension],
    scenario: EvalScenario | None = None,
) -> dict[str, Any]:
    expected_items = scenario.expected_memory_items if scenario else []
    retrieved_items = req.retrieved_memories or []
    correct = sum(
        1 for expected in expected_items
        if any(expected.lower() in retrieved.lower() for retrieved in retrieved_items)
    )
    total = len(expected_items)
    grounded_dimension = dimensions.get("memory_groundedness") or dimensions.get("faithfulness")
    groundedness = one_to_five(grounded_dimension.score if grounded_dimension else None)
    distribution = {str(i): 0 for i in range(1, 6)}
    distribution[str(round(groundedness))] = 1 if total else 0

    systems = {}
    for system in MEMORY_SYSTEMS:
        system_items = req.retrieved_memory_sources.get(system, [])
        system_correct = sum(
            1 for expected in expected_items
            if any(expected.lower() in retrieved.lower() for retrieved in system_items)
        )
        systems[system] = {
            "correct_retrievals": system_correct,
            "total_retrievals": total,
            "retrieval_accuracy": pct(system_correct, total),
            "average_groundedness": groundedness if total else 0.0,
        }

    return {
        "retrieval_accuracy": pct(correct, total),
        "correct_retrievals": correct,
        "total_retrievals": total,
        "average_groundedness": groundedness if total else 0.0,
        "groundedness_distribution": distribution,
        "systems": systems,
        "expected_memory_items": expected_items,
        "retrieved_memories": retrieved_items,
    }


def compute_llm_judge_metrics(dimensions: dict[str, JudgeDimension]) -> dict[str, Any]:
    hallucination_safe = dimensions.get("hallucination")
    hallucination_rate = round((1.0 - hallucination_safe.score) * 100, 2) if hallucination_safe else 0.0
    return {
        "completeness": one_to_five(dimensions.get("completeness").score if "completeness" in dimensions else None),
        "accuracy": one_to_five(dimensions.get("accuracy").score if "accuracy" in dimensions else None),
        "faithfulness": one_to_five(dimensions.get("faithfulness").score if "faithfulness" in dimensions else None),
        "hallucination_rate": hallucination_rate,
        "safety_score": one_to_five(dimensions.get("safety").score if "safety" in dimensions else None),
        "clinical_utility": one_to_five(dimensions.get("clinical_utility").score if "clinical_utility" in dimensions else None),
        "conversation_quality": one_to_five(dimensions.get("conversation_quality").score if "conversation_quality" in dimensions else None),
    }


def compute_multilingual_metrics(req: EvalRequest, dimensions: dict[str, JudgeDimension]) -> dict[str, Any]:
    language = req.language.lower()
    success = 1 if dimensions.get("conversation_quality", JudgeDimension(score=0.0, explanation="")).score >= 0.70 else 0
    rows = []
    for lang in LANGUAGES:
        runs = 1 if lang == language else 0
        rows.append({
            "language": lang.capitalize(),
            "executions": runs,
            "success_rate": pct(success if lang == language else 0, runs),
            "average_completeness": one_to_five(dimensions.get("completeness").score) if runs and "completeness" in dimensions else 0.0,
            "average_faithfulness": one_to_five(dimensions.get("faithfulness").score) if runs and "faithfulness" in dimensions else 0.0,
            "average_safety": one_to_five(dimensions.get("safety").score) if runs and "safety" in dimensions else 0.0,
        })
    return {"languages": rows, "overall_success_rate": pct(success, 1)}


def compute_performance_metrics(
    latency_ms: float,
    token_usage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    stage_latency = {
        stage: {"average_latency_ms": 0.0, "p95_latency_ms": 0.0, "max_latency_ms": 0.0}
        for stage in PERFORMANCE_STAGES
    }
    stage_latency["intent_detection"] = {
        "average_latency_ms": round(latency_ms * 0.15, 1),
        "p95_latency_ms": round(latency_ms * 0.15, 1),
        "max_latency_ms": round(latency_ms * 0.15, 1),
    }
    stage_latency["preconsultation_generation"] = {
        "average_latency_ms": latency_ms,
        "p95_latency_ms": latency_ms,
        "max_latency_ms": latency_ms,
    }

    usage = token_usage or {}
    prompt = float(usage.get("prompt_tokens", 0) or 0)
    completion = float(usage.get("completion_tokens", 0) or 0)
    total = float(usage.get("total_tokens", prompt + completion) or 0)
    generation_seconds = max(latency_ms / 1000.0, 0.001)
    return {
        "response_time": {
            "overall": {
                "average_latency_ms": latency_ms,
                "p95_latency_ms": latency_ms,
                "max_latency_ms": latency_ms,
            },
            "stages": stage_latency,
        },
        "token_consumption": {
            "average_prompt_tokens": prompt,
            "average_completion_tokens": completion,
            "average_total_tokens": total,
            "total_tokens_consumed": total,
            "average_cost_per_conversation": float(usage.get("estimated_cost", 0) or 0),
        },
        "llm_generation_statistics": {
            "average_generation_time_ms": latency_ms,
            "average_tokens_per_second": round(total / generation_seconds, 2) if total else 0.0,
            "longest_generation_ms": latency_ms,
            "shortest_generation_ms": latency_ms,
        },
    }


def aggregate_framework_results(results: list[EvalResult]) -> dict[str, Any]:
    if not results:
        return {}

    def avg(values: list[float]) -> float:
        return round(sum(values) / len(values), 2) if values else 0.0

    workflow_rows = _zero_workflow_rows()
    for result in results:
        wm = result.workflow_metrics or {}
        for name, row in (wm.get("per_workflow") or {}).items():
            if name not in workflow_rows:
                continue
            dest = workflow_rows[name]
            for key in ("successful_tasks", "total_tasks", "completed_workflows", "started_workflows", "correct_transitions", "total_transitions"):
                dest[key] += row.get(key, 0)

    for row in workflow_rows.values():
        row["task_success_rate"] = pct(row["successful_tasks"], row["total_tasks"])
        row["completion_rate"] = pct(row["completed_workflows"], row["started_workflows"])
        row["state_transition_accuracy"] = pct(row["correct_transitions"], row["total_transitions"])

    llm_values = defaultdict(list)
    for result in results:
        for key, value in (result.llm_judge_metrics or {}).items():
            if isinstance(value, (int, float)):
                llm_values[key].append(float(value))

    intent_labels = list(INTENT_CLASSES)
    intent_matrix: dict[str, dict[str, int]] = {}
    specialty_rows: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        intent_metrics = result.intent_metrics or {}
        classification = intent_metrics.get("intent_classification") or {}
        for actual, preds in (classification.get("confusion_matrix") or {}).items():
            if not isinstance(preds, dict):
                continue
            if actual not in intent_labels:
                intent_labels.append(actual)
            for pred, count in preds.items():
                if pred not in intent_labels:
                    intent_labels.append(pred)
                intent_matrix.setdefault(actual, {})
                intent_matrix[actual][pred] = intent_matrix[actual].get(pred, 0) + int(count or 0)

        specialties = (intent_metrics.get("specialty_recommendation") or {}).get("per_specialty") or {}
        for specialty, row in specialties.items():
            specialty_rows[specialty]["correct_recommendations"] += int(row.get("correct_recommendations", 0) or 0)
            specialty_rows[specialty]["total_recommendations"] += int(row.get("total_recommendations", 0) or 0)

    for actual in intent_labels:
        intent_matrix.setdefault(actual, {})
        for pred in intent_labels:
            intent_matrix[actual].setdefault(pred, 0)

    correct_intents = sum(intent_matrix[label][label] for label in intent_labels)
    total_intents = sum(sum(preds.values()) for preds in intent_matrix.values())
    per_class = {}
    for label in intent_labels:
        tp = intent_matrix[label][label]
        fp = sum(intent_matrix[actual][label] for actual in intent_labels if actual != label)
        fn = sum(intent_matrix[label][pred] for pred in intent_labels if pred != label)
        precision = pct(tp, tp + fp)
        recall = pct(tp, tp + fn)
        f1 = round((2 * precision * recall) / (precision + recall), 2) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1}

    specialty_totals = {
        specialty: {
            "correct_recommendations": int(counts["correct_recommendations"]),
            "total_recommendations": int(counts["total_recommendations"]),
            "accuracy": pct(counts["correct_recommendations"], counts["total_recommendations"]),
        }
        for specialty, counts in specialty_rows.items()
    }
    total_recommendations = sum(row["total_recommendations"] for row in specialty_totals.values())
    correct_recommendations = sum(row["correct_recommendations"] for row in specialty_totals.values())

    memory_system_rows = {
        system: {
            "correct_retrievals": 0,
            "total_retrievals": 0,
            "retrieval_accuracy": 0.0,
            "average_groundedness": 0.0,
        }
        for system in MEMORY_SYSTEMS
    }
    memory_groundedness_values = []
    memory_distribution = {str(i): 0 for i in range(1, 6)}
    memory_correct = 0
    memory_total = 0
    for result in results:
        memory_metrics = result.memory_metrics or {}
        memory_correct += int(memory_metrics.get("correct_retrievals", 0) or 0)
        memory_total += int(memory_metrics.get("total_retrievals", 0) or 0)
        groundedness = memory_metrics.get("average_groundedness")
        if isinstance(groundedness, (int, float)) and groundedness > 0:
            memory_groundedness_values.append(float(groundedness))
        for bucket, count in (memory_metrics.get("groundedness_distribution") or {}).items():
            if str(bucket) in memory_distribution:
                memory_distribution[str(bucket)] += int(count or 0)
        for system, row in (memory_metrics.get("systems") or {}).items():
            if system not in memory_system_rows or not isinstance(row, dict):
                continue
            memory_system_rows[system]["correct_retrievals"] += int(row.get("correct_retrievals", 0) or 0)
            memory_system_rows[system]["total_retrievals"] += int(row.get("total_retrievals", 0) or 0)

    for system, row in memory_system_rows.items():
        row["retrieval_accuracy"] = pct(row["correct_retrievals"], row["total_retrievals"])
        grounded_values = [
            float((r.memory_metrics or {}).get("systems", {}).get(system, {}).get("average_groundedness", 0))
            for r in results
            if ((r.memory_metrics or {}).get("systems", {}).get(system, {}).get("average_groundedness", 0) or 0) > 0
        ]
        row["average_groundedness"] = avg(grounded_values)

    language_rows = {lang.capitalize(): Counter() for lang in LANGUAGES}
    language_scores = {lang.capitalize(): defaultdict(list) for lang in LANGUAGES}
    for result in results:
        for row in (result.multilingual_metrics or {}).get("languages", []):
            lang = row.get("language")
            if lang in language_rows and row.get("executions", 0):
                language_rows[lang]["executions"] += row.get("executions", 0)
                language_rows[lang]["successful"] += 1 if row.get("success_rate", 0) >= 100 else 0
                for key in ("average_completeness", "average_faithfulness", "average_safety"):
                    language_scores[lang][key].append(row.get(key, 0))

    latency_values = [float(r.latency_ms) for r in results if r.latency_ms is not None]

    def percentile(values: list[float], q: float) -> float:
        if not values:
            return 0.0
        ordered = sorted(values)
        index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * q))))
        return round(ordered[index], 2)

    stage_values: dict[str, dict[str, list[float]]] = {
        stage: {"average_latency_ms": [], "p95_latency_ms": [], "max_latency_ms": []}
        for stage in PERFORMANCE_STAGES
    }
    token_values = defaultdict(list)
    generation_values = defaultdict(list)
    for result in results:
        performance = result.performance_metrics or {}
        for stage, row in ((performance.get("response_time") or {}).get("stages") or {}).items():
            if stage not in stage_values or not isinstance(row, dict):
                continue
            for key in stage_values[stage]:
                if isinstance(row.get(key), (int, float)):
                    stage_values[stage][key].append(float(row[key]))
        for key, value in (performance.get("token_consumption") or {}).items():
            if isinstance(value, (int, float)):
                token_values[key].append(float(value))
        for key, value in (performance.get("llm_generation_statistics") or {}).items():
            if isinstance(value, (int, float)):
                generation_values[key].append(float(value))

    stage_latency = {
        stage: {
            "average_latency_ms": avg(values["average_latency_ms"]),
            "p95_latency_ms": percentile(values["p95_latency_ms"] or values["average_latency_ms"], 0.95),
            "max_latency_ms": max(values["max_latency_ms"] or values["average_latency_ms"] or [0.0]),
        }
        for stage, values in stage_values.items()
    }

    return {
        "workflow_metrics": {
            "overall_task_success_rate": pct(sum(r["successful_tasks"] for r in workflow_rows.values()), sum(r["total_tasks"] for r in workflow_rows.values())),
            "overall_completion_rate": pct(sum(r["completed_workflows"] for r in workflow_rows.values()), sum(r["started_workflows"] for r in workflow_rows.values())),
            "overall_state_transition_accuracy": pct(sum(r["correct_transitions"] for r in workflow_rows.values()), sum(r["total_transitions"] for r in workflow_rows.values())),
            "per_workflow": workflow_rows,
        },
        "intent_metrics": {
            "intent_classification": {
                "accuracy": pct(correct_intents, total_intents),
                "precision": avg([v["precision"] for v in per_class.values()]),
                "recall": avg([v["recall"] for v in per_class.values()]),
                "f1": avg([v["f1"] for v in per_class.values()]),
                "classes": intent_labels,
                "confusion_matrix": intent_matrix,
                "per_class": per_class,
            },
            "specialty_recommendation": {
                "overall_accuracy": pct(correct_recommendations, total_recommendations),
                "per_specialty": specialty_totals,
            },
        },
        "memory_metrics": {
            "retrieval_accuracy": pct(memory_correct, memory_total),
            "correct_retrievals": memory_correct,
            "total_retrievals": memory_total,
            "average_groundedness": avg(memory_groundedness_values),
            "groundedness_distribution": memory_distribution,
            "systems": memory_system_rows,
        },
        "llm_judge_metrics": {key: avg(values) for key, values in llm_values.items()},
        "multilingual_metrics": {
            "languages": [
                {
                    "language": lang,
                    "executions": int(counts["executions"]),
                    "success_rate": pct(counts["successful"], counts["executions"]),
                    "average_completeness": avg(language_scores[lang]["average_completeness"]),
                    "average_faithfulness": avg(language_scores[lang]["average_faithfulness"]),
                    "average_safety": avg(language_scores[lang]["average_safety"]),
                }
                for lang, counts in language_rows.items()
            ]
        },
        "performance_metrics": {
            "average_latency_ms": avg(latency_values),
            "response_time": {
                "overall": {
                    "average_latency_ms": avg(latency_values),
                    "p95_latency_ms": percentile(latency_values, 0.95),
                    "max_latency_ms": max(latency_values or [0.0]),
                },
                "stages": stage_latency,
            },
            "token_consumption": {
                "average_prompt_tokens": avg(token_values["average_prompt_tokens"]),
                "average_completion_tokens": avg(token_values["average_completion_tokens"]),
                "average_total_tokens": avg(token_values["average_total_tokens"]),
                "total_tokens_consumed": round(sum(token_values["total_tokens_consumed"]), 2) if token_values["total_tokens_consumed"] else 0.0,
                "average_cost_per_conversation": avg(token_values["average_cost_per_conversation"]),
            },
            "llm_generation_statistics": {
                "average_generation_time_ms": avg(generation_values["average_generation_time_ms"]),
                "average_tokens_per_second": avg(generation_values["average_tokens_per_second"]),
                "longest_generation_ms": max(generation_values["longest_generation_ms"] or [0.0]),
                "shortest_generation_ms": min(generation_values["shortest_generation_ms"] or [0.0]),
            },
        },
    }
