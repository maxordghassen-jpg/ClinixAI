import asyncio
import logging
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config.settings import settings
from app.memory.memory_manager import MemoryManager
from app.memory.redis_memory import RedisMemory
from app.repositories.chat_history_repo import ChatHistoryRepository
from app.repositories.memory_repo import MemoryRepository
from app.repositories.patient_profile_repo import PatientProfileRepository
from app.repositories.preconsultation_repo import PreconsultationRepository
from app.repositories.preconsultation_report_repo import PreconsultationReportRepository
from graphs.doctor.navigation_graph import DoctorGraph
from graphs.patient.patient_graph import build_patient_graph
from graphs.shared.schemas import AgentState

logger = logging.getLogger(__name__)

router = APIRouter(tags=["agents"])

memory              = RedisMemory()
_memory_repo        = MemoryRepository()
_memory_manager     = MemoryManager()
_preconsult_repo    = PreconsultationRepository()
_report_repo        = PreconsultationReportRepository()
_history_repo       = ChatHistoryRepository()
_patient_profile_repo = PatientProfileRepository()
patient_graph       = build_patient_graph()


# ── JWT identity extraction ───────────────────────────────────────────────────

def _extract_identity(authorization: str | None) -> dict:
    """
    Decode the Bearer JWT and return identity claims.
    Returns {} when the header is absent, malformed, or the secret is not configured.
    The agent service does NOT reject bad tokens — it falls back to whatever the
    request body provides. The auth service is the authoritative gatekeeper.
    """
    if not authorization or not authorization.startswith("Bearer "):
        return {}
    if not settings.JWT_SECRET:
        return {}
    token = authorization[7:]
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return {
            "patient_profile_id": payload.get("patient_profile_id"),
            "doctor_id":          payload.get("doctor_id"),
            "role":               payload.get("role"),
            "name":               payload.get("name"),
            "email":              payload.get("sub"),
        }
    except JWTError as exc:
        logger.debug(f"[AUTH] JWT decode failed (non-fatal): {exc}")
        return {}


# ── Request schema ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message:         str
    session_id:      str | None = None
    doctor_id:       str | None = None
    patient_id:      str | None = None
    appointment_id:  str | None = None
    latitude:        float | None = None
    longitude:       float | None = None


# ── Doctor chat ───────────────────────────────────────────────────────────────

@router.post("/doctor/chat")
async def doctor_chat(
    payload: ChatRequest,
    authorization: str | None = Header(default=None),
):
    identity = _extract_identity(authorization)
    # JWT identity wins; request body is fallback for legacy/unauthenticated calls
    doctor_id = identity.get("doctor_id") or payload.doctor_id

    session_id = f"doctor:{doctor_id}" if doctor_id else payload.session_id

    result = await DoctorGraph.run(
        message=payload.message,
        doctor_id=doctor_id,
        session_id=session_id,
        appointment_id=payload.appointment_id,
    )

    return result


# ── Patient chat ──────────────────────────────────────────────────────────────

@router.post("/patient/chat")
async def patient_chat(
    payload: ChatRequest,
    authorization: str | None = Header(default=None),
):
    print("\n\n######## PATIENT CHAT HIT ########", flush=True)
    print(payload.model_dump(), flush=True)

    identity = _extract_identity(authorization)
    patient_id = identity.get("patient_profile_id") or payload.patient_id

    # Resolve slug-based JWT ids ("patient-{slug}") to the canonical UUID-based
    # patient_profiles document when one exists for the same email — keeps
    # agent_service reads/writes aligned with the document auth_service's
    # "My Profile" page resolves to.
    if patient_id:
        patient_id = await _patient_profile_repo.resolve_patient_id(
            patient_id, identity.get("email")
        )

    # Namespace session key by role so Redis keys never collide across user types
    session_id = f"patient:{patient_id}" if patient_id else payload.session_id

    state = AgentState(
        role="patient",
        message=payload.message,
        session_id=session_id,
        patient_id=patient_id,
        doctor_id=payload.doctor_id,
        appointment_id=payload.appointment_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        memory={},
        response="",
    )

    try:
        result = await patient_graph.ainvoke(state)

        # Normalise result — LangGraph may return a Pydantic model or a dict
        if isinstance(result, dict):
            response_text = result.get("response") or ""
            memory_dict   = result.get("memory") or {}
            ui_action     = result.get("ui_action")
            ui_payload    = result.get("ui_payload")
        else:
            response_text = getattr(result, "response", None) or ""
            memory_dict   = getattr(result, "memory", {}) or {}
            ui_action     = getattr(result, "ui_action", None)
            ui_payload    = getattr(result, "ui_payload", None)

        # Ensure memory_dict is JSON-safe (Redis deserialization is reliable,
        # but guard against any non-serialisable stragglers from older keys)
        try:
            import json as _json
            _json.dumps(memory_dict)
        except (TypeError, ValueError):
            logger.warning(
                "patient memory contained non-serialisable value(s) — returning {}",
            )
            memory_dict = {}

    except Exception:
        logger.exception(
            "patient_graph.ainvoke unhandled error | session=%s message=%r",
            session_id, payload.message,
        )
        return {
            "response": "I'm sorry, something went wrong on my end. Please try again.",
            "memory": {},
        }

    response_body: dict = {
        "response": response_text,
        "memory":   memory_dict,
    }

    if ui_action:
        response_body["ui_action"]  = ui_action
        response_body["ui_payload"] = ui_payload

    return response_body


# ── Preconsultation latest ────────────────────────────────────────────────────

@router.get("/preconsultation/{patient_id}/latest")
async def get_latest_preconsultation(
    patient_id: str,
    authorization: str | None = Header(default=None),
):
    """
    Return the most recent preconsultation summary for a patient.

    Accessible by:
      - the patient themselves (patient_profile_id matches)
      - any doctor (access control is handled at the doctor-view layer)
    Returns 404 when no preconsultation entry exists yet.
    """
    from fastapi import HTTPException
    identity  = _extract_identity(authorization)
    caller_id = identity.get("patient_profile_id") or identity.get("doctor_id")
    role = identity.get("role", "")

    # Patients may only fetch their own entry
    if role == "patient" and caller_id and caller_id != patient_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    doc = await _preconsult_repo.get_latest(patient_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No preconsultation found")
    return doc


# ── Pre-consultation reports ──────────────────────────────────────────────────

@router.get("/reports/appointment/{appointment_id}")
async def get_report_for_appointment(
    appointment_id: str,
    authorization: str | None = Header(default=None),
):
    """
    Return the pre-consultation report for a specific appointment.
    Accessible by:
      - the doctor whose doctor_id is on the report
      - any doctor (doctors may view any patient's report for now)
      - the patient whose patient_id is on the report
    """
    from fastapi import HTTPException
    identity = _extract_identity(authorization)
    role = identity.get("role", "")
    if not role:
        raise HTTPException(status_code=401, detail="Authentication required")

    doc = await _report_repo.get_by_appointment(appointment_id)
    if not doc:
        raise HTTPException(status_code=404, detail="No report found for this appointment")

    # Patients may only read reports for their own appointments
    if role == "patient":
        caller_pid = identity.get("patient_profile_id")
        if caller_pid and caller_pid != doc.get("patient_id"):
            raise HTTPException(status_code=403, detail="Forbidden")

    return doc


@router.get("/reports/patient/{patient_id}")
async def list_reports_for_patient(
    patient_id: str,
    authorization: str | None = Header(default=None),
):
    """
    Return all pre-consultation reports for a patient, most-recent first.
    Doctors only — patients use the single-appointment endpoint.
    """
    from fastapi import HTTPException
    identity = _extract_identity(authorization)
    role = identity.get("role", "")
    if role != "doctor":
        raise HTTPException(status_code=403, detail="Doctors only")

    docs = await _report_repo.get_by_patient(patient_id)
    return docs


# ── Clear memory ──────────────────────────────────────────────────────────────

@router.delete("/memory/{session_id}")
async def clear_memory(session_id: str):
    await memory.clear(session_id)
    return {"message": "Memory cleared"}


# ── Longitudinal memory read ──────────────────────────────────────────────────

@router.get("/memory/user/{user_id}")
async def get_user_memory(
    user_id: str,
    q: str | None = None,              # optional semantic query string
    authorization: str | None = Header(default=None),
):
    """
    Return the user's structured long-term memories, semantic recommendations,
    and pending workflow snapshot.

    Optional query param ?q= triggers semantic retrieval so the frontend can
    surface contextually relevant memories (e.g., ?q=cardiology specialist).
    """
    from fastapi import HTTPException
    from graphs.shared.memory_context_builder import MemoryContextBuilder

    identity  = _extract_identity(authorization)
    caller_id = identity.get("patient_profile_id") or identity.get("doctor_id")
    if identity and caller_id and caller_id != user_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    memories, pending_workflow = await asyncio.gather(
        _memory_repo.get_ranked_memories(user_id, limit=20),
        _memory_repo.get_pending_workflow(user_id),
        return_exceptions=True,
    )
    if isinstance(memories, BaseException):
        memories = []
    if isinstance(pending_workflow, BaseException):
        pending_workflow = None

    # Semantic retrieval if a query is provided
    semantic: list = []
    if q and isinstance(memories, list):
        try:
            semantic = await _memory_manager.load_semantic(user_id, q)
        except Exception:
            semantic = []

    # Doctor recommendations from affinity + semantic signals
    recommendations = MemoryContextBuilder.build_doctor_recommendations(
        long_term=memories if isinstance(memories, list) else [],
        semantic=semantic,
    )

    return {
        "user_id":           user_id,
        "memories":          memories,
        "semantic_memories": semantic,
        "recommendations":   recommendations,
        "pending_workflow":  pending_workflow,
    }


# ── Chat history ──────────────────────────────────────────────────────────────


class SaveChatHistoryRequest(BaseModel):
    user_id:   str
    user_role: str          # "patient" | "doctor"
    session_id: str
    messages:  list[dict[str, Any]]
    language:  str = "en"


def _resolve_user_id(identity: dict, url_or_body_id: str) -> str:
    """
    Return the authoritative user_id for every chat-history endpoint.

    The JWT (decoded into `identity`) is always preferred because it contains
    the UUID that the auth-service wrote after its slug→UUID migration.  The
    Zustand store on the frontend can hold a stale slug-based ID from an older
    login session, which would cause a mismatch and wrongly return 403.

    Fallback order:
      1. JWT patient_profile_id  (patient accounts)
      2. JWT doctor_id           (doctor accounts)
      3. URL / body user_id      (unauthenticated / legacy callers)
    """
    caller_id = identity.get("patient_profile_id") or identity.get("doctor_id")
    return caller_id or url_or_body_id


@router.post("/chat/history/save", status_code=204)
async def save_chat_history(
    payload: SaveChatHistoryRequest,
    authorization: str | None = Header(default=None),
):
    """Upsert a conversation by session_id. Called by the frontend after each turn."""
    identity = _extract_identity(authorization)
    user_id  = _resolve_user_id(identity, payload.user_id)

    logger.debug(
        "[ChatHistory] save | user=%s role=%s session=%s msgs=%d",
        user_id, payload.user_role, payload.session_id, len(payload.messages),
    )
    await _history_repo.upsert_conversation(
        user_id=user_id,
        user_role=payload.user_role,
        session_id=payload.session_id,
        messages=payload.messages,
        language=payload.language,
    )


@router.get("/chat/history/{user_role}/{user_id}")
async def list_chat_history(
    user_role: str,
    user_id: str,
    authorization: str | None = Header(default=None),
):
    """List conversation summaries (no messages) for a user, newest first."""
    identity         = _extract_identity(authorization)
    effective_user   = _resolve_user_id(identity, user_id)

    return await _history_repo.list_conversations(
        user_id=effective_user, user_role=user_role
    )


@router.get("/chat/history/{user_role}/{user_id}/{session_id}")
async def get_chat_history_session(
    user_role: str,
    user_id: str,
    session_id: str,
    authorization: str | None = Header(default=None),
):
    """Return a full conversation with all messages."""
    identity       = _extract_identity(authorization)
    effective_user = _resolve_user_id(identity, user_id)

    doc = await _history_repo.get_conversation(
        user_id=effective_user, user_role=user_role, session_id=session_id
    )
    if doc is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return doc


@router.delete("/chat/history/{user_role}/{user_id}/{session_id}", status_code=204)
async def delete_chat_history_session(
    user_role: str,
    user_id: str,
    session_id: str,
    authorization: str | None = Header(default=None),
):
    """Delete one conversation by session_id."""
    identity       = _extract_identity(authorization)
    effective_user = _resolve_user_id(identity, user_id)

    await _history_repo.delete_conversation(
        user_id=effective_user, user_role=user_role, session_id=session_id
    )


@router.delete("/chat/history/{user_role}/{user_id}", status_code=204)
async def delete_all_chat_history(
    user_role: str,
    user_id: str,
    authorization: str | None = Header(default=None),
):
    """Delete ALL conversations for a user."""
    identity       = _extract_identity(authorization)
    effective_user = _resolve_user_id(identity, user_id)

    await _history_repo.delete_all_conversations(
        user_id=effective_user, user_role=user_role
    )
