"""
rerun_fallbacks.py — re-run only results that hit Groq rate limits.

Identifies all-0.50 documents (rate-limit fallback) and all-null documents
(evaluation error), deletes them, and replaces with fresh real scores.

Timing: 60 s sleep between scenarios — allows the 12 000 TPM Groq counter
to fully reset between each run.

Usage:
    cd evaluation_service
    ..\venv\Scripts\python.exe rerun_fallbacks.py
"""

import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, ".")

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.config.settings import settings
from app.db.mongo_client import connect, disconnect, get_db
from evaluators.orchestrator import run_evaluation
from schemas.eval_schemas import EvalRequest, WorkflowContext
from datasets.eval_scenarios import SCENARIOS, SCENARIO_INDEX

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)

# ── Same preconsultation data as seed_all_scenarios.py ────────────────────────

_PRECONSULT_SYMPTOM_DATA: dict[str, dict] = {
    "PRECONSULT-001": {
        "chief_complaint": "severe headache",
        "duration": "",
        "severity": None,
        "associated_symptoms": [],
        "urgency": "medium",
        "specialty_recommended": "neurologist",
        "ai_summary": "Patient reports severe headache. Duration and severity not yet collected.",
    },
    "PRECONSULT-002": {
        "chief_complaint": "severe headache",
        "duration": "3 days",
        "severity": 7,
        "associated_symptoms": [],
        "urgency": "medium",
        "specialty_recommended": "neurologist",
        "ai_summary": (
            "Patient reports severe headache for 3 days, severity 7/10. "
            "Associated symptoms not yet collected."
        ),
    },
    "PRECONSULT-003": {
        "chief_complaint": "severe headache",
        "duration": "3 days",
        "severity": 7,
        "associated_symptoms": ["nausea", "dizziness"],
        "urgency": "medium",
        "specialty_recommended": "neurologist",
        "ai_summary": (
            "Patient presents with severe headache for 3 days, severity 7/10, "
            "associated with nausea and dizziness. Urgency: medium. "
            "Recommended specialty: neurology."
        ),
    },
    "PRECONSULT-004": {
        "chief_complaint": "symptomes non precises",
        "duration": "",
        "severity": None,
        "associated_symptoms": [],
        "urgency": "low",
        "specialty_recommended": "medecin generaliste",
        "ai_summary": "Patient souhaite decrire ses symptomes. Questionnaire demarre.",
    },
    "PRECONSULT-005": {
        "chief_complaint": "stomach pain",
        "duration": "not yet collected",
        "severity": None,
        "associated_symptoms": [],
        "urgency": "medium",
        "specialty_recommended": "gastroenterologist",
        "ai_summary": (
            "Patient with known Crohn's disease and aspirin allergy reports stomach pain. "
            "Duration not yet collected. Profile flagged for physician review."
        ),
    },
    "PRECONSULT-006": {
        "chief_complaint": "chest pain and shortness of breath",
        "duration": "1 hour",
        "severity": 9,
        "associated_symptoms": ["shortness of breath"],
        "urgency": "high",
        "specialty_recommended": "emergency",
        "ai_summary": (
            "URGENT: Patient reports chest pain and shortness of breath for 1 hour, "
            "severity 9/10. Red-flag symptoms. Immediate emergency care recommended."
        ),
    },
}

_PRECONSULT_WF_STATES: dict[str, dict] = {
    "PRECONSULT-001": {"step": "collecting_chief_complaint"},
    "PRECONSULT-002": {
        "step": "collecting_severity",
        "symptom_chief_complaint": "severe headache",
        "symptom_duration": "3 days",
    },
    "PRECONSULT-003": {
        "step": "collecting_associated",
        "symptom_chief_complaint": "severe headache",
        "symptom_duration": "3 days",
        "symptom_severity": 7,
    },
    "PRECONSULT-004": {"step": "collecting_chief_complaint"},
    "PRECONSULT-005": {
        "step": "collecting_duration",
        "symptom_chief_complaint": "stomach pain",
    },
    "PRECONSULT-006": {
        "step": "collecting_duration",
        "symptom_chief_complaint": "chest pain and shortness of breath",
    },
}


def _build_request(scenario) -> EvalRequest:
    is_preconsult = scenario.id.startswith("PRECONSULT")
    sym_data = _PRECONSULT_SYMPTOM_DATA.get(scenario.id) if is_preconsult else None
    wf_state = _PRECONSULT_WF_STATES.get(scenario.id, {}) if is_preconsult else {}

    wf_ctx = None
    if scenario.expected_tool or scenario.expected_workflow or is_preconsult:
        wf_ctx = WorkflowContext(
            expected_tool=scenario.expected_tool,
            expected_action=scenario.expected_workflow or (
                "preconsultation" if is_preconsult else None
            ),
            workflow_state=wf_state,
        )

    ctx = scenario.context or ""
    if is_preconsult and sym_data:
        summary_line = f"AI summary: {sym_data.get('ai_summary', '')}. "
        ctx = summary_line + ctx if ctx else summary_line

    return EvalRequest(
        scenario_id=scenario.id,
        user_message=scenario.user_message,
        agent_response=scenario.reference_response or scenario.user_message,
        reference_response=scenario.reference_response,
        language=scenario.language,
        role=scenario.role,
        workflow=wf_ctx,
        context=ctx or None,
        symptom_data=sym_data,
        include_preconsultation=is_preconsult,
        include_bert_score=False,
        include_rouge=False,
        include_bleu=False,
        include_em=False,
        include_esm=False,
        include_answer_metrics=False,
        include_context_precision=False,
    )


def _is_fallback(doc: dict) -> bool:
    """True when all four judge scores are exactly 0.5 (rate-limit neutral value)."""
    keys = [
        "safety_score",
        "answer_relevancy_judge",
        "answer_correctness_judge",
        "groundedness_score",
    ]
    return all(doc.get(k) == 0.5 for k in keys)


def _is_null_result(doc: dict) -> bool:
    """True when safety_score is None (evaluation crashed entirely)."""
    return doc.get("safety_score") is None


def _is_real(result) -> bool:
    """True when the new result has at least one score different from 0.5."""
    scores = [
        result.safety_score,
        result.answer_relevancy_judge,
        result.answer_correctness_judge,
        result.groundedness_score,
    ]
    return any(s is not None and s != 0.5 for s in scores)


async def find_fallback_scenario_ids(col) -> list[str]:
    """
    Return unique scenario_ids that have at least one fallback or null document,
    ordered by scenario catalogue order.
    """
    # All-0.50 documents
    q_bad = {
        "safety_score": 0.5,
        "answer_relevancy_judge": 0.5,
        "answer_correctness_judge": 0.5,
        "groundedness_score": 0.5,
    }
    # Null (error) documents
    q_null = {"safety_score": None}

    cursor_bad  = col.find(q_bad,  {"scenario_id": 1})
    cursor_null = col.find(q_null, {"scenario_id": 1})

    bad_ids  = {d["scenario_id"] for d in await cursor_bad.to_list(length=500)
                if d.get("scenario_id")}
    null_ids = {d["scenario_id"] for d in await cursor_null.to_list(length=500)
                if d.get("scenario_id")}

    all_ids = bad_ids | null_ids

    # Keep original catalogue order
    ordered = [s.id for s in SCENARIOS if s.id in all_ids]
    return ordered


async def delete_fallbacks_for(col, scenario_id: str) -> int:
    """
    Delete all fallback/null documents for scenario_id.
    Returns count of deleted documents.
    """
    q_bad = {
        "scenario_id": scenario_id,
        "safety_score": 0.5,
        "answer_relevancy_judge": 0.5,
        "answer_correctness_judge": 0.5,
        "groundedness_score": 0.5,
    }
    q_null = {"scenario_id": scenario_id, "safety_score": None}

    r1 = await col.delete_many(q_bad)
    r2 = await col.delete_many(q_null)
    return r1.deleted_count + r2.deleted_count


async def save_result_direct(col, result) -> str:
    """Insert EvalResult into MongoDB, return inserted_id as str."""
    from app.services.result_store import _to_doc
    doc = _to_doc(result)
    res = await col.insert_one(doc)
    return str(res.inserted_id)


async def main():
    print(f"\n{'='*62}")
    print(f"  ClinixAI — Fallback Re-runner  |  {datetime.now():%Y-%m-%d %H:%M}")
    print(f"  Sleep between scenarios: 60 s")
    print(f"{'='*62}\n")

    await connect(settings.MONGODB_URI, settings.MONGODB_DB)
    db  = get_db()
    col = db["evaluation_results"]

    # ── Step 1: find what needs re-running ───────────────────────────────────
    to_rerun = await find_fallback_scenario_ids(col)
    print(f"Fallback scenarios found : {len(to_rerun)}")
    for sid in to_rerun:
        print(f"  {sid}")
    print()

    if not to_rerun:
        print("Nothing to re-run. All results look real.")
        await disconnect()
        return

    # ── Step 2: re-run one by one ─────────────────────────────────────────────
    HDR = "{:<3} {:<16} {:<14} {:<8} {:>5} {:>5} {:>5} {:>5} {:>5} {:>5} {:>8}  {}"
    SEP = "-" * 96
    print(HDR.format(
        "#", "ID", "Category", "Language",
        "Safe", "Hal%", "Relev", "Corr", "Gnd", "WF", "Overall", "Status",
    ))
    print(SEP)

    replaced  = []
    still_bad = []
    failed    = []

    for idx, sid in enumerate(to_rerun, 1):
        scenario = SCENARIO_INDEX.get(sid)
        if scenario is None:
            print(f"  {idx:>3} {sid:<16} NOT IN CATALOGUE — skipped")
            failed.append(sid)
            continue

        req = _build_request(scenario)

        try:
            result = await run_evaluation(req)

            # Set workflow_success_rate
            if req.workflow and result.workflow_score is not None:
                result.workflow_success_rate = (
                    1.0 if result.workflow_score >= 0.70 else 0.0
                )

            def f(v):
                return "{:.2f}".format(v) if v is not None else "  --"

            if _is_real(result):
                # Delete all old fallback docs for this scenario, save new one
                deleted = await delete_fallbacks_for(col, sid)
                new_id  = await save_result_direct(col, result)
                result.id = new_id
                replaced.append(sid)
                status = f"REPLACED (deleted {deleted} old)"
            else:
                # Still hitting rate limits — don't delete the old one, log
                still_bad.append(sid)
                status = "STILL 0.50 — kept old result"

            print(HDR.format(
                idx, sid, scenario.category[:14], scenario.language,
                f(result.safety_score),
                f(result.hallucination_risk),
                f(result.answer_relevancy_judge),
                f(result.answer_correctness_judge),
                f(result.groundedness_score),
                f(result.workflow_score),
                f(result.overall_score),
                status,
            ))

        except Exception as exc:
            print(f"  {idx:>3} {sid:<16} ERROR: {exc}")
            failed.append(sid)

        # 60 s sleep between scenarios — except after the last one
        if idx < len(to_rerun):
            remaining = len(to_rerun) - idx
            print(f"       sleeping 60 s  ({remaining} scenario(s) left) …")
            await asyncio.sleep(60)

    print(SEP)
    print(f"\n  Replaced   : {len(replaced)}")
    if still_bad:
        print(f"  Still 0.50 : {len(still_bad)} — {still_bad}")
    if failed:
        print(f"  Errors     : {len(failed)} — {failed}")

    # ── Step 3: final aggregated table ───────────────────────────────────────
    print(f"\n{'='*62}")
    print("  FINAL RESULTS TABLE (only replaced scenarios)")
    print(f"{'='*62}")

    # Fetch the fresh docs we just saved
    if replaced:
        fresh_cursor = col.find(
            {"scenario_id": {"$in": replaced}},
            {
                "_id": 0, "scenario_id": 1, "language": 1, "role": 1,
                "safety_score": 1, "hallucination_risk": 1,
                "answer_relevancy_judge": 1, "answer_correctness_judge": 1,
                "groundedness_score": 1, "workflow_score": 1,
                "workflow_success_rate": 1, "overall_score": 1,
            },
        ).sort("scenario_id", 1)
        fresh_docs = await fresh_cursor.to_list(length=200)

        # Attach category from catalogue
        cat_map = {s.id: s.category for s in SCENARIOS}
        for d in fresh_docs:
            if not d.get("category") and d.get("scenario_id"):
                d["category"] = cat_map.get(d["scenario_id"], "unknown")

        def avg(lst, key):
            vals = [d[key] for d in lst if d.get(key) is not None]
            return sum(vals) / len(vals) if vals else None

        # Per-row table
        FHDR = "{:<16} {:<14} {:<8} {:>5} {:>5} {:>5} {:>5} {:>5} {:>5} {:>7}"
        print(FHDR.format(
            "ID", "Category", "Language",
            "Safe", "Hal%", "Relev", "Corr", "Gnd", "WF", "Overall"
        ))
        print("-" * 85)
        for d in fresh_docs:
            def f(k): return "{:.2f}".format(d[k]) if d.get(k) is not None else "  --"
            print(FHDR.format(
                d.get("scenario_id", "?")[:16],
                d.get("category", "?")[:14],
                d.get("language", "?")[:8],
                f("safety_score"), f("hallucination_risk"),
                f("answer_relevancy_judge"), f("answer_correctness_judge"),
                f("groundedness_score"), f("workflow_score"), f("overall_score"),
            ))

        # By language
        print()
        langs = sorted({d.get("language", "?") for d in fresh_docs})
        LHDR  = "{:<10} {:>3} {:>6} {:>6} {:>6} {:>6} {:>6} {:>6} {:>7}"
        print("BY LANGUAGE")
        print(LHDR.format("Language", "N", "Safe", "Hal%",
                           "Relev", "Corr", "Gnd", "WF", "Overall"))
        print("-" * 65)
        for lang in langs:
            sub = [d for d in fresh_docs if d.get("language") == lang]
            def af(k): v = avg(sub, k); return "{:.3f}".format(v) if v is not None else "  N/A"
            print(LHDR.format(lang, len(sub),
                af("safety_score"), af("hallucination_risk"),
                af("answer_relevancy_judge"), af("answer_correctness_judge"),
                af("groundedness_score"), af("workflow_score"), af("overall_score")))

        # By category
        print()
        cats = sorted({d.get("category", "unknown") for d in fresh_docs})
        CHDR  = "{:<18} {:>3} {:>6} {:>6} {:>6} {:>6} {:>6} {:>6} {:>7}"
        print("BY CATEGORY")
        print(CHDR.format("Category", "N", "Safe", "Hal%",
                           "Relev", "Corr", "Gnd", "WF", "Overall"))
        print("-" * 73)
        for cat in cats:
            sub = [d for d in fresh_docs if d.get("category") == cat]
            def af(k): v = avg(sub, k); return "{:.3f}".format(v) if v is not None else "  N/A"
            wfs_sub = [d for d in sub if d.get("workflow_success_rate") is not None]
            wf_avg  = avg(wfs_sub, "workflow_success_rate")
            print(CHDR.format(cat[:18], len(sub),
                af("safety_score"), af("hallucination_risk"),
                af("answer_relevancy_judge"), af("answer_correctness_judge"),
                af("groundedness_score"), af("workflow_score"), af("overall_score")))

    await disconnect()
    print(f"\n  Done — {datetime.now():%H:%M:%S}")
    print(f"  Dashboard: http://127.0.0.1:8007/dashboard")
    print(f"  CSV:       GET http://127.0.0.1:8007/results/export/csv\n")


if __name__ == "__main__":
    asyncio.run(main())
