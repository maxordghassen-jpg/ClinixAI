"""
Language-switch validation — IntentNode language-preservation guard
(agent_service/graphs/shared/nodes/intent_node.py).

Scenario:
    An established French conversation (memory["language"] = "french"),
    not inside an active preconsultation questionnaire (step="idle"),
    sends a new message in Arabic:

        أبحث عن طبيب أطفال   ("I'm looking for a pediatrician")

Expected:
    The language-preservation guard only applies when
    current_step is in _PRECONSULTATION_ACTIVE_STEPS. Here step="idle",
    so the guard does NOT fire, and the LLM-detected language ("arabic")
    is merged into memory["language"] normally -> conversation switches
    to Arabic.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import graphs.shared.nodes.intent_node as intent_node_module  # noqa: E402
from graphs.shared.nodes.intent_node import IntentNode  # noqa: E402
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
    intent_node_module.client = _FakeClient(json.dumps(extracted))


async def main() -> None:
    ok = True

    state = AgentState(
        role="patient",
        message="أبحث عن طبيب أطفال",
        session_id="validation-french-to-arabic-switch",
        memory={
            "step": "idle",
            "language": "french",
        },
    )

    _mock_llm({
        "intent": "doctor_search",
        "specialty": "pediatrician",
        "language": "arabic",
    })

    print("Before IntentNode: language=%r step=%r" %
          (state.memory.get("language"), state.memory.get("step")))

    await IntentNode().run(state)

    print("After IntentNode:  language=%r step=%r intent=%r specialty=%r" %
          (state.memory.get("language"), state.memory.get("step"),
           state.memory.get("intent"), state.memory.get("specialty")))

    if state.memory.get("language") != "arabic":
        ok = False
        print(f"FAIL: memory['language']={state.memory.get('language')!r}, expected 'arabic'")

    print()
    if ok:
        print("PASS: language switched from 'french' to 'arabic' for a new "
              "Arabic message outside an active preconsultation step")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
