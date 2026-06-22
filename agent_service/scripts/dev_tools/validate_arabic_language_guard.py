"""
Arabic multilingual validation — language-preservation guard in IntentNode
(agent_service/graphs/shared/nodes/intent_node.py).

Scenario (Arabic booking flow):
    أبحث عن طبيب أطفال
    -> choose doctor
    -> choose date
    -> choose time
    -> symptom (chief complaint)
    -> duration
    -> severity = "5"

By the time the patient answers "5" for severity, the conversation has
established memory["language"] = "arabic" and
memory["step"] = "collecting_severity_booking" (an active preconsultation /
booking step). The LLM, given the bare numeric reply "5" with no Arabic-script
signal, returns language="english".

Expected (per the new guard):
    * IntentNode preserves memory["language"] = "arabic" (does NOT overwrite
      it with the LLM's "english" guess), because current_step is in
      _ACTIVE_WORKFLOW_STEPS_FOR_LANGUAGE.
    * SymptomCollectionHandler._collect_severity_booking then renders the
      next preconsultation question (collecting_associated_booking) in
      Arabic.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import graphs.shared.nodes.intent_node as intent_node_module  # noqa: E402
from graphs.shared.nodes.intent_node import IntentNode  # noqa: E402
from graphs.patient.handlers.symptom_handler import (  # noqa: E402
    SymptomCollectionHandler,
    PRECONSULT_QUESTIONS,
)
from graphs.shared.schemas import AgentState  # noqa: E402


# ── Fake Groq client (same pattern as validate_phase2.py) ───────────────────

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
    intent_node_module.client = _FakeClient(json.dumps(extracted))


class _FakeRedisMemory:
    async def update(self, session_id, values):
        return {}

    async def delete_keys(self, session_id, keys):
        return None


async def main() -> None:
    ok = True

    # State as of the "5" turn: established Arabic conversation, mid-booking
    # preconsultation, doctor/date/time already selected, chief complaint and
    # duration already collected.
    state = AgentState(
        role="patient",
        message="5",
        session_id="validation-arabic-language-guard",
        memory={
            "step": "collecting_severity_booking",
            "language": "arabic",
            "intent": "preconsultation",
            "specialty": "pediatrician",
            "doctor_id": "6a0c323c0072c8dec428fcbf",
            "doctor_name": "Cabinet de Pediatrie Dr MHIRI Kais",
            "date": "2026-06-15",
            "time": "10:00",
            "symptom_chief_complaint": "حمى",
            "symptom_duration": "يومين",
        },
    )

    # Observed LLM behaviour for a bare numeric reply: no Arabic-script
    # signal, so it defaults language to english.
    _mock_llm({"intent": "preconsultation", "language": "english"})

    print("Before IntentNode: language=%r step=%r" %
          (state.memory.get("language"), state.memory.get("step")))

    await IntentNode().run(state)

    print("After IntentNode:  language=%r step=%r intent=%r" %
          (state.memory.get("language"), state.memory.get("step"), state.memory.get("intent")))

    if state.memory.get("language") != "arabic":
        ok = False
        print(f"FAIL: memory['language']={state.memory.get('language')!r}, expected 'arabic'")

    handler = SymptomCollectionHandler(redis_memory=_FakeRedisMemory())
    await handler.handle(state)

    print("After SymptomCollectionHandler: step=%r" % state.memory.get("step"))
    print()
    print("response shown to user:")
    print(state.response)
    print()

    if state.memory.get("step") != "collecting_associated_booking":
        ok = False
        print(f"FAIL: step={state.memory.get('step')!r}, expected 'collecting_associated_booking'")

    expected_arabic = PRECONSULT_QUESTIONS["collecting_associated"]["arabic"]
    english_text = PRECONSULT_QUESTIONS["collecting_associated"]["english"]

    if state.response != expected_arabic:
        ok = False
        print("FAIL: response is not the Arabic associated-symptoms question")
    if state.response == english_text:
        ok = False
        print("FAIL: response is the English associated-symptoms question")

    print()
    if ok:
        print("PASS: language preserved as 'arabic' across the ambiguous "
              "severity reply; associated-symptoms question rendered in Arabic")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
