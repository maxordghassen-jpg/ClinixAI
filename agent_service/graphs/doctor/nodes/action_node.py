from graphs.doctor.handlers.appointments_handler import AppointmentsHandler
from graphs.doctor.handlers.availability_handler import AvailabilityHandler
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


class ActionNode:
    def __init__(self) -> None:
        self._appointments = AppointmentsHandler()
        self._availability = AvailabilityHandler()

    async def run(self, state: AgentState) -> AgentState:
        tool = state.intent.tool if state.intent else "unknown"
        trace("DOCTOR-ACTION", state.session_id, f"tool={tool!r}")

        if tool == "appointments":
            state.tool_result = await self._appointments.handle(state)
        elif tool == "availability":
            state.tool_result = await self._availability.handle(state)
        else:
            trace("DOCTOR-ACTION", state.session_id, f"unrecognised tool: {tool!r}")
            state.tool_result = {"message": "I could not find a tool for this request."}

        return state
