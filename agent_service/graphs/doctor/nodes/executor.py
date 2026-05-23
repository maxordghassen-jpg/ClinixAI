from graphs.doctor.registries.tools_registry import ToolsRegistry
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


class Executor:

    def __init__(self):
        self.registry = ToolsRegistry()

    async def run(self, state: AgentState) -> AgentState:

        tool_name = state.selected_tool or "unknown"
        action = state.intent.action if state.intent else "unknown"

        trace("DOCTOR-EXEC", state.session_id,
              f"tool={tool_name!r} action={action!r}")

        tool = self.registry.get(tool_name)
        if not tool:
            trace("DOCTOR-EXEC", state.session_id,
                  f"no tool found for {tool_name!r}")
            state.tool_result = {"message": "I could not find a tool for this request."}
            return state

        try:
            state.tool_result = await tool.run(state)
            trace("DOCTOR-EXEC", state.session_id,
                  f"tool execution complete | result type={type(state.tool_result).__name__}")
        except Exception as exc:
            trace("DOCTOR-EXEC", state.session_id,
                  f"tool execution ERROR: {exc}")
            state.tool_result = {
                "message": f"An error occurred while processing your request: {exc}"
            }

        return state
