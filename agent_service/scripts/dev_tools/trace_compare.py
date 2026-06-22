"""
Trace comparison: real-UI-equivalent request (A, patient_id="7698")
vs fresh isolated session (B, no patient_id) — same message.

Replicates the /patient/chat endpoint body from app/api/routes/agent_routes.py
so all node-level trace() output (MEMORY/INTENT/WORKFLOW/ACTION/WRITER) prints
to this process's stdout.
"""
import asyncio
import json

from app.repositories.patient_profile_repo import PatientProfileRepository
from graphs.patient.patient_graph import build_patient_graph
from graphs.shared.schemas import AgentState

MESSAGE = "I want to book an appointment with Dr MHIRI Kais"

patient_graph = build_patient_graph()
_patient_profile_repo = PatientProfileRepository()


async def run_request(label: str, patient_id: str | None, session_id: str | None):
    print(f"\n{'='*20} REQUEST {label} | patient_id={patient_id!r} {'='*20}")

    if patient_id:
        resolved = await _patient_profile_repo.resolve_patient_id(patient_id, None)
        print(f"[TRACE_COMPARE] resolve_patient_id({patient_id!r}) -> {resolved!r}")
        patient_id = resolved

    sid = f"patient:{patient_id}" if patient_id else session_id
    print(f"[TRACE_COMPARE] session_id={sid!r}")

    state = AgentState(
        role="patient",
        message=MESSAGE,
        session_id=sid,
        patient_id=patient_id,
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

    print(f"[TRACE_COMPARE] RESPONSE = {response_text!r}")
    print(f"[TRACE_COMPARE] step={memory_dict.get('step')!r} "
          f"intent={memory_dict.get('intent')!r} "
          f"doctor_id={memory_dict.get('doctor_id')!r} "
          f"doctor_name={memory_dict.get('doctor_name')!r} "
          f"specialty={memory_dict.get('specialty')!r} "
          f"query={memory_dict.get('query')!r}")


async def main():
    await run_request("B (fresh/isolated)", patient_id=None, session_id="trace_b_fresh_2")
    await run_request("A (real UI, patient_id=7698)", patient_id="7698", session_id=None)


asyncio.run(main())
