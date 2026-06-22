from typing import Any, Literal

from pydantic import BaseModel


Role = Literal["doctor", "patient"]
ToolName = Literal[
    "appointments",
    "availability",
    "events",
    "patients",
    "medical_places",
    "medical_profile",
    "report",
    "unknown",
]


class IntentResult(BaseModel):
    tool: ToolName = "unknown"
    action: str = "unknown"
    language: str = "unknown"
    confidence: float = 0.0
    entities: dict[str, Any] = {}
    status: str | None = None


class AgentState(BaseModel):
    role: Role
    message: str
    session_id: str
    doctor_id: str | None = None
    patient_id: str | None = None
    appointment_id: str | None = None
    intent: IntentResult | None = None
    selected_tool: str | None = None
    memory: dict[str, Any] = {}
    # Long-term patient intelligence from MongoDB patient_profiles — read-only this turn.
    profile: dict[str, Any] = {}

    # Ranked cross-session memories from MongoDB user_memories — read-only this turn.
    long_term_memories: list[dict[str, Any]] = []

    # Pre-built context string injected into the IntentNode LLM prompt.
    # Built by MemoryContextBuilder at turn start. Empty string = no personalization.
    memory_context: str = ""

    # Pending workflow snapshot — offered for resume when no active Redis session exists.
    pending_workflow: dict[str, Any] | None = None

    tool_result: Any = None
    response: str | None = None
    # Ephemeral: keys extracted from the current message by IntentNode.
    # Populated once per turn, never persisted to Redis, never written by StateWriterNode.
    # Used by ActionNode to distinguish "just extracted" from "loaded from Redis cache".
    extracted_this_turn: set[str] = set()
    # Ephemeral UI directives — set by handlers, returned in the API response,
    # never persisted to Redis. The frontend reads these to drive UI orchestration
    # (e.g. open the map, focus a doctor card, trigger a booking panel).
    ui_action: str | None = None
    ui_payload: dict[str, Any] | None = None
    # User's real-world coordinates — forwarded from the browser on every request
    # when the patient has granted location permission. Never persisted to Redis.
    # Used by geo handlers to perform proximity-aware searches.
    latitude:  float | None = None
    longitude: float | None = None
    # Completed preconsultation data for this turn (set by SymptomCollectionHandler).
    # Ephemeral — not persisted to Redis; the permanent record lives in preconsultation_data.
    symptom_data: dict[str, Any] | None = None
