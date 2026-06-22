"""
Run all evaluation scenarios against the thesis framework and save results.

Usage:
  cd evaluation_service
  ..\venv\Scripts\python.exe seed_all_scenarios.py
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, ".")

from app.config.settings import settings
from app.db.mongo_client import connect, disconnect
from app.services.result_store import save_result
from datasets.eval_scenarios import SCENARIOS
from evaluators.framework_metrics import aggregate_framework_results
from evaluators.orchestrator import run_evaluation
from schemas.eval_schemas import EvalRequest, EvalResult, WorkflowContext

logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)-8s %(message)s")

PRECONSULT_SYMPTOM_DATA: dict[str, dict] = {
    "PRECONSULT-001": {
        "chief_complaint": "severe headache",
        "duration": "",
        "severity": None,
        "associated_symptoms": [],
        "ai_summary": "Patient reports severe headache. Duration and severity not yet collected.",
    },
    "PRECONSULT-002": {
        "chief_complaint": "severe headache",
        "duration": "3 days",
        "severity": 7,
        "associated_symptoms": [],
        "ai_summary": "Patient reports severe headache for 3 days, severity 7/10.",
    },
    "PRECONSULT-003": {
        "chief_complaint": "severe headache",
        "duration": "3 days",
        "severity": 7,
        "associated_symptoms": ["nausea", "dizziness"],
        "ai_summary": "Patient presents with severe headache for 3 days, severity 7/10, with nausea and dizziness.",
    },
    "PRECONSULT-004": {
        "chief_complaint": "symptomes non precises",
        "duration": "",
        "severity": None,
        "associated_symptoms": [],
        "ai_summary": "Patient souhaite decrire ses symptomes. Questionnaire demarre.",
    },
    "PRECONSULT-005": {
        "chief_complaint": "stomach pain",
        "duration": "not yet collected",
        "severity": None,
        "associated_symptoms": [],
        "ai_summary": "Patient with Crohn's disease and aspirin allergy reports stomach pain.",
    },
    "PRECONSULT-006": {
        "chief_complaint": "chest pain and shortness of breath",
        "duration": "1 hour",
        "severity": 9,
        "associated_symptoms": ["shortness of breath"],
        "ai_summary": "Urgent chest pain and shortness of breath for 1 hour. Immediate care recommended.",
    },
}

PRECONSULT_WORKFLOW_STATES: dict[str, dict] = {
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
    "PRECONSULT-005": {"step": "collecting_duration", "symptom_chief_complaint": "stomach pain"},
    "PRECONSULT-006": {"step": "collecting_duration", "symptom_chief_complaint": "chest pain and shortness of breath"},
}


def build_request(scenario) -> EvalRequest:
    is_preconsult = scenario.id.startswith("PRECONSULT")
    symptom_data = PRECONSULT_SYMPTOM_DATA.get(scenario.id) if is_preconsult else None
    workflow_state = PRECONSULT_WORKFLOW_STATES.get(scenario.id, {}) if is_preconsult else {}

    workflow = None
    if scenario.expected_tool or scenario.expected_workflow or is_preconsult:
        workflow = WorkflowContext(
            expected_tool=scenario.expected_tool,
            expected_action=scenario.expected_workflow or ("preconsultation" if is_preconsult else None),
            workflow_state=workflow_state,
        )

    context = scenario.context or ""
    if symptom_data:
        context = f"AI summary: {symptom_data.get('ai_summary', '')}. {context}".strip()

    return EvalRequest(
        scenario_id=scenario.id,
        user_message=scenario.user_message,
        agent_response=scenario.reference_response or scenario.user_message,
        reference_response=scenario.reference_response,
        language=scenario.language,
        role=scenario.role,
        workflow=workflow,
        context=context or None,
        symptom_data=symptom_data,
        include_preconsultation=is_preconsult,
        include_bert_score=False,
        include_rouge=False,
        include_bleu=False,
        include_em=False,
        include_esm=False,
        include_answer_metrics=False,
        include_context_precision=False,
    )


async def main() -> None:
    print("=" * 80)
    print(f"ClinixAI thesis evaluation seeder - {datetime.now():%Y-%m-%d %H:%M}")
    print(f"Scenarios: {len(SCENARIOS)}")
    print("=" * 80)

    await connect(settings.MONGODB_URI, settings.MONGODB_DB)

    results: list[EvalResult] = []
    failed: list[str] = []

    header = "{:<4} {:<18} {:<18} {:>7} {:>7} {:>7} {:>7} {:>7} {:>8}"
    print(header.format("#", "ID", "Category", "TSR", "Faith", "Safety", "Utility", "Hall%", "Latency"))
    print("-" * 88)

    for index, scenario in enumerate(SCENARIOS, 1):
        try:
            result = await run_evaluation(build_request(scenario))
            result.id = await save_result(result)
            results.append(result)

            wm = result.workflow_metrics or {}
            lm = result.llm_judge_metrics or {}
            print(header.format(
                index,
                scenario.id,
                scenario.category,
                f"{wm.get('overall_task_success_rate', 0):.1f}",
                f"{lm.get('faithfulness', 0):.1f}",
                f"{lm.get('safety_score', 0):.1f}",
                f"{lm.get('clinical_utility', 0):.1f}",
                f"{lm.get('hallucination_rate', 0):.1f}",
                f"{result.latency_ms or 0:.0f}ms",
            ))
        except Exception as exc:
            failed.append(scenario.id)
            print(f"{index:<4} {scenario.id:<18} ERROR: {exc}")

        if index < len(SCENARIOS):
            await asyncio.sleep(15)

    await disconnect()

    aggregate = aggregate_framework_results(results)
    workflow = aggregate.get("workflow_metrics", {})
    llm = aggregate.get("llm_judge_metrics", {})
    performance = aggregate.get("performance_metrics", {})

    print("-" * 88)
    print(f"Saved: {len(results)}")
    if failed:
        print(f"Failed: {failed}")
    print()
    print("Global thesis metrics")
    print(f"  Task Success Rate:          {workflow.get('overall_task_success_rate', 0):.2f}%")
    print(f"  Workflow Completion Rate:   {workflow.get('overall_completion_rate', 0):.2f}%")
    print(f"  State Transition Accuracy:  {workflow.get('overall_state_transition_accuracy', 0):.2f}%")
    print(f"  Completeness:               {llm.get('completeness', 0):.2f} / 5")
    print(f"  Accuracy:                   {llm.get('accuracy', 0):.2f} / 5")
    print(f"  Faithfulness:               {llm.get('faithfulness', 0):.2f} / 5")
    print(f"  Hallucination Rate:         {llm.get('hallucination_rate', 0):.2f}%")
    print(f"  Safety Score:               {llm.get('safety_score', 0):.2f} / 5")
    print(f"  Clinical Utility:           {llm.get('clinical_utility', 0):.2f} / 5")
    print(f"  Conversation Quality:       {llm.get('conversation_quality', 0):.2f} / 5")
    print(f"  Average Latency:            {performance.get('average_latency_ms', 0):.0f}ms")
    print()
    print("Dashboard: http://127.0.0.1:8007/dashboard")


if __name__ == "__main__":
    asyncio.run(main())
