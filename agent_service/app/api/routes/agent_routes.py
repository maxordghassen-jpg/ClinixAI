from fastapi import APIRouter

from pydantic import BaseModel

from graphs.patient.patient_graph import (
    build_patient_graph,
)

from graphs.doctor.navigation_graph import (
    DoctorGraph,
)

from graphs.shared.schemas import (
    AgentState,
)

from app.memory.redis_memory import (
    RedisMemory,
)


# =====================================================
# Router
# =====================================================

router = APIRouter(
    tags=["agents"]
)

# =====================================================
# Memory
# =====================================================

memory = RedisMemory()

# =====================================================
# Graphs
# =====================================================

patient_graph = (
    build_patient_graph()
)

# =====================================================
# Request Schema
# =====================================================


class ChatRequest(BaseModel):

    message: str

    session_id: str | None = None

    doctor_id: str | None = None

    patient_id: str | None = None

    appointment_id: str | None = None


# =====================================================
# DOCTOR CHAT
# =====================================================


@router.post("/doctor/chat")
async def doctor_chat(
    payload: ChatRequest,
):

    return await DoctorGraph.run(

        message=payload.message,

        doctor_id=payload.doctor_id,

        session_id=payload.session_id,

        appointment_id=payload.appointment_id,
    )


# =====================================================
# PATIENT CHAT
# =====================================================


@router.post("/patient/chat")
async def patient_chat(
    payload: ChatRequest,
):

    state = AgentState(

        role="patient",

        message=payload.message,

        session_id=(
            payload.session_id
            or payload.patient_id
        ),

        patient_id=payload.patient_id,

        doctor_id=payload.doctor_id,

        appointment_id=(
            payload.appointment_id
        ),

        memory={},

        response="",
    )

    result = await patient_graph.ainvoke(
        state
    )

    return {

        "response":
        result["response"],

        "memory":
        result["memory"],
    }


# =====================================================
# CLEAR MEMORY
# =====================================================


@router.delete(
    "/memory/{session_id}"
)
async def clear_memory(
    session_id: str,
):

    await memory.clear(
        session_id
    )

    return {
        "message":
        "Memory cleared"
    }