from graphs.patient.mcp.tool_caller import (
    ToolCaller,
)


class DoctorSearchService:

    def __init__(self):

        self.tools = ToolCaller()

    async def search(
        self,
        specialty: str,
    ):

        # IMPORTANT:
        # Pass STRING only
        # NOT dict

        results = await (
            self.tools.search_places(
                specialty
            )
        )

        # Normalize response
        if isinstance(
            results,
            dict,
        ):

            return results.get(
                "results",
                []
            )

        return results