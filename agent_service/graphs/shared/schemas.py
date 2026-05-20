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
    tool_result: Any = None
    response: str | None = None
