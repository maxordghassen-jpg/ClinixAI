"""
B-2 validation — IntentNode's cross-session resume guard (MED-3) must not
restore a stale, COMPLETED preconsultation into a brand-new booking, while a
genuinely in-progress questionnaire keeps its collected answers.

Scenario A: an abandoned booking snapshot whose own step is a post-
            questionnaire booking step (awaiting_date) carries
            preconsultation_done=True + symptom_* + recommended_specialty.
            None of those 6 fields may be merged into a new booking.

Scenario B: Redis session memory already holds an in-progress questionnaire
            step (collecting_duration) with symptom_chief_complaint set.
            The MED-3 merge must not run at all — the in-progress answers
            (and step) must be left untouched, and the unrelated pending
            booking snapshot must not leak doctor_id into memory.

Scenario C: defensive check on the new filter's "keep" branch — if a resumed
            snapshot's OWN step is one of _PRECONSULTATION_ACTIVE_STEPS, its
            symptom fields must NOT be stripped.

The Groq client is replaced with a fake that returns a fixed JSON response,
so each scenario is deterministic and runs without network access.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

import graphs.shared.nodes.intent_node as intent_node_module  # noqa: E402
from graphs.shared.nodes.intent_node import (  # noqa: E402
    IntentNode,
    _PRECONSULTATION_ACTIVE_STEPS,
    _STALE_PRECONSULT_FIELDS,
)
from graphs.shared.schemas import AgentState  # noqa: E402


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str) -> None:
        self._content = content

    async def create(self, *args, **kwargs):
        return _FakeResponse(self._content)


class _FakeChat:
    def __init__(self, content: str) -> None:
        self.completions = _FakeCompletions(content)


class _FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = _FakeChat(content)


def _mock_llm(extracted: dict) -> None:
    """Replace the module-level Groq client with one that always returns
    `extracted` as the LLM's JSON output."""
    intent_node_module.client = _FakeClient(json.dumps(extracted))


STALE_FIELDS = sorted(_STALE_PRECONSULT_FIELDS)

# An abandoned booking attempt: the questionnaire finished
# (preconsultation_done=True + symptom_* + recommended_specialty) but the
# booking itself stalled at awaiting_date — a step NOT in
# _PRECONSULTATION_ACTIVE_STEPS.
SNAP_STALE_BOOKING = {
    "step": "awaiting_date",
    "intent": "booking",
    "doctor_id": "doc-999",
    "preconsultation_done": True,
    "symptom_chief_complaint": "chest pain",
    "symptom_duration": "3 days",
    "symptom_severity": "severe",
    "symptom_associated": "shortness of breath",
    "recommended_specialty": "cardiologue",
}

# A snapshot whose OWN step is genuinely mid-questionnaire.
SNAP_IN_PROGRESS_PRECONSULT = {
    "step": "collecting_duration_booking",
    "intent": "preconsultation",
    "symptom_chief_complaint": "fever",
}


async def scenario_a() -> bool:
    _mock_llm({"intent": "booking", "specialty": "pediatrician", "language": "english"})

    state = AgentState(
        role="patient",
        message="I need a pediatrician",
        session_id="validation-b2-a",
        memory={},
        pending_workflow={"workflow_type": "booking", "state": dict(SNAP_STALE_BOOKING)},
    )

    await IntentNode().run(state)

    ok = True
    for key in STALE_FIELDS:
        if key in state.memory:
            ok = False
            print(f"FAIL: scenario A - stale field leaked: {key}={state.memory[key]!r}")
    if ok:
        print("PASS: scenario A - none of the 6 stale preconsultation fields were merged")
    print(f"       resulting memory keys: {sorted(state.memory.keys())}")
    return ok


async def scenario_b() -> bool:
    _mock_llm({"intent": "none", "language": "english"})

    state = AgentState(
        role="patient",
        message="3 days",
        session_id="validation-b2-b",
        memory={
            "step": "collecting_duration",
            "intent": "preconsultation",
            "symptom_chief_complaint": "headache",
            "patient_id": "patient-abc",
            "language": "english",
        },
        pending_workflow={"workflow_type": "booking", "state": dict(SNAP_STALE_BOOKING)},
    )

    await IntentNode().run(state)

    ok = True
    if state.memory.get("step") != "collecting_duration":
        ok = False
        print(f"FAIL: scenario B - step changed to {state.memory.get('step')!r}")
    if state.memory.get("symptom_chief_complaint") != "headache":
        ok = False
        print(
            "FAIL: scenario B - symptom_chief_complaint lost/changed: "
            f"{state.memory.get('symptom_chief_complaint')!r}"
        )
    if "doctor_id" in state.memory:
        ok = False
        print(f"FAIL: scenario B - pending booking snapshot leaked doctor_id={state.memory['doctor_id']!r}")
    if ok:
        print("PASS: scenario B - in-progress questionnaire state preserved, pending snapshot ignored")
    print(f"       resulting memory keys: {sorted(state.memory.keys())}")
    return ok


async def scenario_c() -> bool:
    _mock_llm({"intent": "none", "language": "english"})

    assert SNAP_IN_PROGRESS_PRECONSULT["step"] in _PRECONSULTATION_ACTIVE_STEPS

    state = AgentState(
        role="patient",
        message="ok",
        session_id="validation-b2-c",
        memory={},
        pending_workflow={"workflow_type": "preconsultation", "state": dict(SNAP_IN_PROGRESS_PRECONSULT)},
    )

    await IntentNode().run(state)

    ok = (
        state.memory.get("symptom_chief_complaint") == "fever"
        and state.memory.get("step") == "collecting_duration_booking"
    )
    if ok:
        print("PASS: scenario C - in-progress questionnaire snapshot's own fields preserved on resume")
    else:
        print(
            "FAIL: scenario C - symptom_chief_complaint="
            f"{state.memory.get('symptom_chief_complaint')!r} step={state.memory.get('step')!r}"
        )
    print(f"       resulting memory keys: {sorted(state.memory.keys())}")
    return ok


async def main() -> None:
    results = [
        await scenario_a(),
        await scenario_b(),
        await scenario_c(),
    ]

    print()
    print("ALL PASS" if all(results) else "SOME FAILED")
    if not all(results):
        sys.exit(1)


asyncio.run(main())
