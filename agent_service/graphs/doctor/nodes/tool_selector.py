from graphs.shared.schemas import AgentState


class ToolSelector:
    async def run(self, state: AgentState) -> AgentState:
        state.selected_tool = state.intent.tool if state.intent else "unknown"
        return state
