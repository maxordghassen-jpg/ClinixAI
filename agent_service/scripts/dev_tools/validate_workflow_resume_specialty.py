"""
Workflow-resume specialty overwrite validation — IntentNode
(agent_service/graphs/shared/nodes/intent_node.py).

Scenario:
    A patient sends an Arabic doctor-search message:

        أبحث عن طبيب أطفال   ("I'm looking for a pediatrician")

    1. The LLM (mocked) returns specialty="پدیاتری" (the observed Farsi
       regression value), intent="doctor_search", language="arabic".
    2. SPECIALTY_NORMALIZATION normalizes it to "pédiatre" and
       state.memory.update(extracted) sets memory["specialty"] = "pédiatre".
    3. state.memory.get("step") is empty and a pending_workflow snapshot
       exists (workflow_type="doctor_search", state.specialty="پدیاتری" —
       a STALE value persisted by a prior turn before normalization). The
       cross-session resume guard fires and merges the snapshot.

Expected (per the fix):
    The stale snap["specialty"]="پدیاتری" must NOT overwrite this turn's
    freshly-normalized memory["specialty"]="pédiatre", because "specialty"
    is in state.extracted_this_turn for this turn.

    Final memory["specialty"] == "pédiatre".
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
    intent_node_module.client = _FakeClient(json.dumps(extracted, ensure_ascii=False))


async def main() -> None:
    ok = True

    # Fresh session (no "step" in Redis-loaded memory), but MemoryNode found
    # a pending workflow snapshot from a prior, abandoned doctor_search turn
    # that still carries the un-normalized Farsi specialty.
    state = AgentState(
        role="patient",
        message="أبحث عن طبيب أطفال",
        session_id="validation-workflow-resume-specialty",
        memory={},
        pending_workflow={
            "workflow_type": "doctor_search",
            "state": {
                "step": "searching_doctors",
                "intent": "doctor_search",
                "specialty": "پدیاتری",
                "query": "پدیاتری",
            },
        },
    )

    _mock_llm({
        "intent": "doctor_search",
        "specialty": "پدیاتری",
        "language": "arabic",
    })

    print("Before IntentNode:")
    print(f"  memory.specialty           = {state.memory.get('specialty')!r}")
    print(f"  pending_workflow.specialty  = {state.pending_workflow['state']['specialty']!r}")
    print()

    await IntentNode().run(state)

    print()
    print("After IntentNode:")
    print(f"  memory.specialty = {state.memory.get('specialty')!r}")
    print(f"  memory.step       = {state.memory.get('step')!r}")
    print(f"  memory.intent     = {state.memory.get('intent')!r}")
    print(f"  memory.query      = {state.memory.get('query')!r}")
    print()

    if state.memory.get("specialty") != "pédiatre":
        ok = False
        print(f"FAIL: memory['specialty']={state.memory.get('specialty')!r}, expected 'pédiatre'")

    print()
    if ok:
        print("PASS: stale workflow-snapshot specialty ('پدیاتری') did NOT overwrite "
              "this turn's normalized specialty ('pédiatre')")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
