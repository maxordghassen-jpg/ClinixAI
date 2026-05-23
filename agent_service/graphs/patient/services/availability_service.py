from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.normalizers.date_normalizer import DateNormalizer
from graphs.shared.trace import trace


class AvailabilityService:

    def __init__(self):
        self.tools = ToolCaller()

    async def get_free_slots(
        self,
        doctor_id: str,
        date: str,
    ) -> list:

        # Normalize to ISO YYYY-MM-DD — the availability route expects this format
        try:
            iso_date = DateNormalizer.normalize(date)
        except ValueError:
            trace("AVAIL", doctor_id, f"unparseable date {date!r} — returning empty slots")
            return []

        trace("AVAIL", doctor_id, f"free-slots request | date={date!r} → iso={iso_date!r}")

        response = await self.tools.get_availability(
            f"/availability/{doctor_id}/{iso_date}/free-slots"
        )

        trace("AVAIL", doctor_id, f"free-slots response: {response!r}")

        if isinstance(response, list):
            return response

        if isinstance(response, dict):
            return response.get("free_slots", [])

        return []
