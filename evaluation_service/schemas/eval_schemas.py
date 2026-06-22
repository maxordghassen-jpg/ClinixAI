"""
ClinixAI Evaluation Service — Pydantic schemas.

EvalResult is the central data contract shared by the orchestrator, routes,
MongoDB store, and frontend dashboard.
"""

from typing import Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field


# ── Workflow context ──────────────────────────────────────────────────────────

class WorkflowContext(BaseModel):
    expected_tool:     str | None     = None
    expected_action:   str | None     = None
    workflow_state:    dict[str, Any] = {}
    ui_action:         str | None     = None
    intent_confidence: float | None   = None
    actual_transition_sequence: list[str] | None = None
    trace_unavailable: bool = False


# ── Single-turn evaluation request ───────────────────────────────────────────

class EvalRequest(BaseModel):
    scenario_id:          str | None          = None
    user_message:         str
    agent_response:       str
    reference_response:   str | None          = None
    language:             str                 = "english"
    role:                 str                 = "patient"
    workflow:             WorkflowContext | None = None
    retrieved_memories:   list[str]           = []
    retrieved_memory_sources: dict[str, list[str]] = {}
    predicted_intent:     str | None          = None
    recommended_specialty: str | None         = None
    conversation_history: list[dict]          = []
    context:              str | None          = None
    # Metric toggles
    include_bert_score:        bool = True
    include_rouge:             bool = True
    include_bleu:              bool = False
    include_em:                bool = True
    include_esm:               bool = True
    include_answer_metrics:    bool = True   # correctness + relevancy
    include_context_precision: bool = True
    # Preconsultation-specific evaluation (requires symptom_data in context)
    include_preconsultation:   bool = False
    symptom_data:              dict[str, Any] | None = None  # collected questionnaire fields
    token_usage:               dict[str, Any] | None = None


# ── Multilingual evaluation request ──────────────────────────────────────────

class MultilingualEvalRequest(BaseModel):
    intent_description: str
    messages:           dict[str, str]
    responses:          dict[str, str]
    workflow_states:    dict[str, dict] = {}


# ── Per-dimension judge output ────────────────────────────────────────────────

class JudgeDimension(BaseModel):
    score:       float
    explanation: str
    confidence:  float = 1.0


# ── Full structured evaluation result ────────────────────────────────────────

class EvalResult(BaseModel):
    # Identity
    id:          str | None = None   # MongoDB _id (set after persistence)
    scenario_id: str | None = None

    # ── LLM Judge dimension scores ────────────────────────────────────────────
    # Safety & grounding (always evaluated)
    hallucination_risk:       float | None = None   # factual hallucination risk 0–1 (inverted)
    groundedness_score:       float | None = None   # retrieval faithfulness 0–1 (higher = better)
    safety_score:             float | None = None
    # Workflow & task
    workflow_score:           float | None = None
    # Conversational
    conversational_quality:   float | None = None
    # Memory & personalisation
    memory_relevance:         float | None = None
    personalization_quality:  float | None = None
    # Domain-specific
    recommendation_quality:   float | None = None
    multilingual_consistency: float | None = None
    # Preconsultation-specific dimensions
    symptom_collection_score:   float | None = None   # completeness of questionnaire
    preconsultation_quality:    float | None = None   # doctor-ready summary quality
    profile_usage_score:        float | None = None   # medical profile used correctly
    # Answer quality (LLM judge dimensions)
    answer_correctness_judge: float | None = None
    answer_relevancy_judge:   float | None = None
    context_precision_judge:  float | None = None
    # System metric: binary workflow completion (1.0 = success, 0.0 = failure)
    workflow_success_rate:    float | None = None

    # Per-dimension detail for drill-down
    dimensions: dict[str, JudgeDimension] = {}

    # ── Lexical / semantic metrics ────────────────────────────────────────────
    bert_score:         float | None = None
    rouge1:             float | None = None
    rouge2:             float | None = None
    rougeL:             float | None = None
    bleu_score:         float | None = None
    exact_match:        float | None = None   # 1.0 or 0.0
    exact_set_match:    float | None = None   # Jaccard ∈ [0,1]
    answer_correctness: float | None = None   # 0.6×sem + 0.4×token_f1
    answer_relevancy:   float | None = None   # question–answer cosine
    context_precision:  float | None = None   # fraction of memories reflected

    # ── Aggregate ─────────────────────────────────────────────────────────────
    overall_score: float | None = None

    # Thesis evaluation framework groups. These are stored separately in MongoDB
    # and embedded here for dashboard/result detail reads.
    workflow_metrics:     dict[str, Any] = {}
    intent_metrics:       dict[str, Any] = {}
    memory_metrics:       dict[str, Any] = {}
    llm_judge_metrics:    dict[str, Any] = {}
    multilingual_metrics: dict[str, Any] = {}
    performance_metrics:  dict[str, Any] = {}

    # ── Provenance ────────────────────────────────────────────────────────────
    judge_explanation: str   = ""
    latency_ms:        float | None = None
    evaluated_at:      str   = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    model_used:        str   = ""

    # Echoed for display
    user_message:      str | None = None
    agent_response:    str | None = None
    reference_response: str | None = None

    # Tags / metadata
    language:  str = "english"
    role:      str = "patient"
    tags:      list[str] = []


# ── Batch evaluation ──────────────────────────────────────────────────────────

class BatchEvalRequest(BaseModel):
    requests: list[EvalRequest]


class BatchEvalResult(BaseModel):
    results:   list[EvalResult]
    aggregate: dict[str, float] = {}


# ── Scenario definition ───────────────────────────────────────────────────────

class EvalScenario(BaseModel):
    id:                        str
    name:                      str
    description:               str
    category:                  str
    language:                  str   = "english"
    role:                      str   = "patient"
    user_message:              str
    expected_workflow:         str | None = None
    expected_tool:             str | None = None
    reference_response:        str | None = None
    context:                   str | None = None
    tags:                      list[str]  = []
    # True when the scenario expects a full workflow to complete successfully
    # (e.g. booking confirmed, cancellation done, preconsultation summary generated).
    # Used to compute workflow_success_rate in the scenario runner.
    expected_workflow_success: bool = False
    expected_intent:              str | None = None
    expected_specialty:           str | None = None
    expected_memory_items:        list[str] = []
    expected_transition_sequence: list[str] = []


# ── History / trend response models ──────────────────────────────────────────

class EvalSummary(BaseModel):
    """Row for the history table — includes all 8 active metrics."""
    id:            str
    scenario_id:   str | None
    # GROUP 1 — LLM Judge
    overall_score:             float | None
    safety_score:              float | None
    hallucination_risk:        float | None
    answer_relevancy_judge:    float | None = None
    answer_correctness_judge:  float | None = None
    groundedness_score:        float | None = None
    # GROUP 2 — System
    workflow_score:            float | None = None
    workflow_success_rate:     float | None = None
    task_success_rate:         float | None = None
    workflow_completion_rate:  float | None = None
    faithfulness:              float | None = None
    clinical_utility:          float | None = None
    # Provenance
    latency_ms:    float | None
    evaluated_at:  str
    model_used:    str
    language:      str
    role:          str


class TrendPoint(BaseModel):
    evaluated_at:             str
    overall_score:            float | None
    # GROUP 1 — LLM Judge
    safety_score:             float | None
    hallucination_risk:       float | None
    answer_relevancy_judge:   float | None = None
    answer_correctness_judge: float | None = None
    groundedness_score:       float | None = None
    # GROUP 2 — System
    workflow_score:           float | None = None
    workflow_success_rate:    float | None = None
    task_success_rate:        float | None = None
    workflow_completion_rate: float | None = None
    faithfulness:             float | None = None
    clinical_utility:         float | None = None
    # GROUP 3 — Multilingual
    multilingual_consistency: float | None = None
    # Provenance
    latency_ms:               float | None
    scenario_id:              str | None


class TrendResponse(BaseModel):
    points:    list[TrendPoint]
    averages:  dict[str, float] = {}
    best_run:  EvalSummary | None = None
    worst_run: EvalSummary | None = None


class CompareRequest(BaseModel):
    id_a: str
    id_b: str


class CompareResult(BaseModel):
    run_a: EvalResult
    run_b: EvalResult
    delta: dict[str, float | None] = {}   # key → (score_b - score_a)
