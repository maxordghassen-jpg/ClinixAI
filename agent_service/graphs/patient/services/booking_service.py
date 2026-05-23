from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.normalizers.date_normalizer import DateNormalizer
from graphs.shared.normalizers.time_normalizer import TimeNormalizer
from graphs.shared.trace import trace


class BookingService:

    def __init__(self):
        self.tools = ToolCaller()

    async def book(
        self,
        doctor_id: str,
        patient_id: str,
        date: str,
        time: str,
    ):
        # Normalize — raise ValueError immediately if either input is unparseable
        # so ActionNode can catch it and handle gracefully (offer alternatives, etc.)
        normalized_date = DateNormalizer.normalize(date)
        normalized_time = TimeNormalizer.normalize(time)

        payload = {
            "doctor_id": str(doctor_id),
            "patient_id": str(patient_id),
            "date": normalized_date,
            "time": normalized_time,
        }

        trace("BOOKING", doctor_id,
              f"booking attempt | date={date!r}→{normalized_date!r} "
              f"time={time!r}→{normalized_time!r} patient={patient_id}")

        response = await self.tools.post_appointments("/appointments", payload)

        trace("BOOKING", doctor_id, f"booking response: {response!r}")

        return response
