"""
MED-3 validation — cross-session workflow snapshot resume.

MemoryNode no longer pre-merges pending_workflow["state"] into session_memory.
IntentNode's new post-LLM guard must merge it back ONLY when:
  (a) this turn's intent is empty/"none" (vague reply to the resume hint), or
  (b) this turn's intent matches the pending workflow's own type.
A brand-new, unrelated intent must NOT inherit the stale snapshot.
"""
import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, ".")

from graphs.shared.nodes import intent_node  # noqa: E402
from graphs.shared.nodes.intent_node import IntentNode  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402

PENDING = {
    "workflow_type": "booking",
    "state": {
        "step": "awaiting_date",
        "specialty": "cardiologue",
        "doctor_id": "abc123",
        "intent": "booking",
    },
}


def llm_response(content: str):
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


async def run_case(name, llm_json, initial_memory, expect_merge):
    intent_node.client.chat.completions.create = AsyncMock(
        return_value=llm_response(llm_json)
    )
    state = AgentState(
        role="patient",
        message="ok",
        session_id="validation-med3-session",
        memory=dict(initial_memory),
        pending_workflow=PENDING,
    )
    result = await IntentNode().run(state)
    merged = result.memory.get("step") == PENDING["state"]["step"]
    ok = merged == expect_merge
    print(
        f"{'PASS' if ok else 'FAIL'}: {name} | "
        f"step={result.memory.get('step')!r} intent={result.memory.get('intent')!r} "
        f"(merged={merged}, expected={expect_merge})"
    )
    return ok


async def main():
    results = []

    # A: brand-new unrelated intent (cancel_appointment) -> no merge
    results.append(await run_case(
        "A unrelated intent (cancel_appointment) -> no merge",
        '{"intent":"cancel_appointment","language":"english"}',
        {},
        expect_merge=False,
    ))

    # B: vague/none intent -> merge (resume)
    results.append(await run_case(
        "B vague intent (none) -> merge/resume",
        '{"intent":"none","language":"english"}',
        {},
        expect_merge=True,
    ))

    # C: intent matches pending workflow_type (booking) -> merge
    results.append(await run_case(
        "C intent matches pending workflow_type (booking) -> merge",
        '{"intent":"booking","specialty":"cardiologue","language":"english"}',
        {},
        expect_merge=True,
    ))

    # D: session already mid-workflow (has step) -> no merge regardless
    results.append(await run_case(
        "D existing active step -> no merge even if intent=none",
        '{"intent":"none","language":"english"}',
        {"step": "selecting_doctor", "intent": "booking"},
        expect_merge=False,
    ))

    print()
    if all(results):
        print("ALL PASS")
    else:
        print("SOME FAILED")
        sys.exit(1)


asyncio.run(main())
