from graphs.patient.mcp.tool_caller import (
    ToolCaller,
)
from graphs.shared.normalizers.specialty_normalizer import SpecialtyNormalizer


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

        query, log_line = SpecialtyNormalizer.normalize_with_log(specialty)

        print(f"[DEBUG-SPECIALTY] DoctorSearchService.search | {log_line}")

        results = await (
            self.tools.search_places(
                query
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