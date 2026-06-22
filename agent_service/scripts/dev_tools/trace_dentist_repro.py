"""
Memory-lifecycle repro: book with Dr MHIRI Kais, then search dentists,
then ask to book with Dr MHIRI Kais again — to find where a stale
specialty/query="Dentiste" survives into the second MHIRI Kais request.

Runs all three turns through the SAME session_id, via the real
patient_graph.ainvoke() pipeline (Redis-backed), exactly like the live
server at localhost:8001.
"""
import asyncio

from graphs.patient.patient_graph import build_patient_graph
from graphs.shared.schemas import AgentState
from app.memory.redis_memory import RedisMemory

SESSION_ID = "trace_dentist_repro_1"

patient_graph = build_patient_graph()


async def turn(label: str, message: str):
    print(f"\n{'='*15} TURN {label}: {message!r} {'='*15}")
    state = AgentState(
        role="patient",
        message=message,
        session_id=SESSION_ID,
        patient_id=None,
        doctor_id=None,
        appointment_id=None,
        latitude=None,
        longitude=None,
        memory={},
        response="",
    )
    result = await patient_graph.ainvoke(state)
    if isinstance(result, dict):
        response_text = result.get("response") or ""
        memory_dict = result.get("memory") or {}
    else:
        response_text = getattr(result, "response", None) or ""
        memory_dict = getattr(result, "memory", {}) or {}

    print(f"[REPRO] RESPONSE = {response_text!r}")
    print(f"[REPRO] memory = {memory_dict}")
    return memory_dict


async def main():
    redis = RedisMemory()
    await redis.clear(SESSION_ID)

    await turn("1 (book MHIRI Kais)", "I want to book an appointment with Dr MHIRI Kais")
    await turn("2 (search dentist)", "I'm looking for a dentist")
    await turn("3 (book MHIRI Kais again)", "I want to book an appointment with Dr MHIRI Kais")

    # Show raw Redis state after turn 3
    raw = await redis.get(SESSION_ID)
    print(f"\n[REPRO] Redis session_memory AFTER turn 3 = {raw}")


asyncio.run(main())
