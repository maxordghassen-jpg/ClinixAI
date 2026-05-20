from graphs.patient.registries.tools_registry import ToolsRegistry
from graphs.shared.schemas import AgentState


class Executor:
    def __init__(self):
        self.registry = ToolsRegistry()

    async def run(self, state: AgentState) -> AgentState:
        tool = self.registry.get(state.selected_tool or "unknown")
        if not tool:
            state.tool_result = {"message": "I could not find a tool for this request."}
            return state
        state.tool_result = await tool.run(state)
        return state
