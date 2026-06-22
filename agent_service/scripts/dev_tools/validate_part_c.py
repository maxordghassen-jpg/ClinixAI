"""
Part C end-to-end validation — flows 2, 3, 4, 5, 6.
Flow 1 (preconsultation -> booking, multi-turn) is in validate_part_c_flow1.py.
"""
import asyncio
import json
import sys

sys.path.insert(0, ".")

from app.db.mongo_client import connect_to_mongo, close_mongo_connection  # noqa: E402
from app.memory.redis_memory import RedisMemory  # noqa: E402
from graphs.patient.patient_graph import build_patient_graph  # noqa: E402
from graphs.doctor.navigation_graph import DoctorGraph  # noqa: E402
from graphs.shared.schemas import AgentState  # noqa: E402

AMIRA_ID = "76985768-4c45-4307-a258-144e07f4fd1a"
DOCTOR_ID = "6a0c323c0072c8dec428fcf7"  # Dr. HANNACHI Iyed (doc-001)

TUNIS_LAT = 36.8065
TUNIS_LNG = 10.1815

redis_memory = RedisMemory()
graph = build_patient_graph()


async def run_turn(session_id, message, patient_id=AMIRA_ID, lat=None, lng=None, memory=None):
    state = AgentState(
        role="patient",
        message=message,
        session_id=session_id,
        memory=memory or {},
        patient_id=patient_id,
        latitude=lat,
        longitude=lng,
    )
    result = await graph.ainvoke(state)
    print(f"\n>>> USER: {message}")
    print(f"<<< ASSISTANT: {result['response']}")
    print(f"    step={result['memory'].get('step')!r} intent={result['memory'].get('intent')!r}")
    return result


async def flow2():
    print("\n" + "=" * 70)
    print("FLOW 2: Direct geo search — 'find a cardiologist near me'")
    print("=" * 70)
    session_id = "e2e-flow2"
    await redis_memory.clear(session_id)
    result = await run_turn(session_id, "find a cardiologist near me", lat=TUNIS_LAT, lng=TUNIS_LNG)
    print("memory:", json.dumps(result["memory"], indent=2, default=str)[:1500])
    print("ui_action:", result.get("ui_action"))
    print("ui_payload pins:", len((result.get("ui_payload") or {}).get("pins", [])))
    await redis_memory.clear(session_id)


async def flow3():
    print("\n" + "=" * 70)
    print("FLOW 3: Direct booking — 'book an appointment with Dr Sarah Mitchell'")
    print("=" * 70)
    session_id = "e2e-flow3"
    await redis_memory.clear(session_id)
    result = await run_turn(session_id, "book an appointment with Dr Sarah Mitchell")
    print("memory:", json.dumps(result["memory"], indent=2, default=str)[:1500])
    await redis_memory.clear(session_id)


async def flow4():
    print("\n" + "=" * 70)
    print("FLOW 4: Existing appointments — 'show my appointments'")
    print("=" * 70)
    session_id = "e2e-flow4"
    await redis_memory.clear(session_id)
    result = await run_turn(session_id, "show my appointments")
    print("memory:", json.dumps(result["memory"], indent=2, default=str)[:1500])
    await redis_memory.clear(session_id)


async def flow5():
    print("\n" + "=" * 70)
    print("FLOW 5: Doctor schedule — 'show my schedule'")
    print("=" * 70)
    session_id = f"doctor:{DOCTOR_ID}"
    await redis_memory.clear(session_id)
    result = await DoctorGraph.run("show my schedule", doctor_id=DOCTOR_ID, session_id=session_id)
    print(f"<<< ASSISTANT: {result['response']}")
    print("memory:", json.dumps(result["memory"], indent=2, default=str)[:1500])
    await redis_memory.clear(session_id)


async def flow6():
    print("\n" + "=" * 70)
    print("FLOW 6: Amira profile load check")
    print("=" * 70)
    session_id = "e2e-flow6"
    await redis_memory.clear(session_id)
    result = await run_turn(session_id, "hello")
    profile = result.get("profile", {})
    for field in ["blood_type", "weight", "height", "smoking_status", "alcohol_consumption",
                   "appointment_history", "preferred_specialties"]:
        val = profile.get(field, "<MISSING>")
        if isinstance(val, list):
            val = f"<list of {len(val)}>"
        print(f"  {field}: {val!r}")
    await redis_memory.clear(session_id)


async def main():
    await connect_to_mongo()
    try:
        for fn in [flow2, flow3, flow4, flow5, flow6]:
            try:
                await fn()
            except Exception:
                print(f"\n!!! {fn.__name__} ERROR")
                import traceback
                traceback.print_exc()
    finally:
        await close_mongo_connection()


asyncio.run(main())
