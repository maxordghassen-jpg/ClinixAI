from graphs.patient.mcp.tool_caller import ToolCaller
from graphs.shared.trace import trace


def _fallback_name(doctor_id: str) -> str:
    return f"Dr. #{doctor_id[:8]}" if doctor_id else "Unknown"


class DoctorNameHydrator:
    """
    Batch-fill doctor_name for appointment records that only carry a doctor_id.

    The appointment service stores only doctor_id (no embedded name).
    This service issues a single batch POST /api/doctors/lookup to the geo_service
    and fills in the name for every appointment missing one.

    Failure is non-fatal: appointments without a resolvable name fall back to
    a short-ID display ("Dr. #6a0c323c") rather than a raw 24-char hex string.
    """

    def __init__(self) -> None:
        self._tools = ToolCaller()

    async def hydrate(
        self,
        appointment_list: list[dict],
        session_id: str = "",
    ) -> list[dict]:
        """
        Fill doctor_name in-place for every appointment missing a human-readable name.
        Returns the same list for chaining.
        """
        missing_ids = list({
            a["doctor_id"]
            for a in appointment_list
            if a.get("doctor_id") and (
                not a.get("doctor_name") or a["doctor_name"] == a["doctor_id"]
            )
        })

        if not missing_ids:
            trace("HYDRATOR", session_id, "all appointments already have doctor names")
            return appointment_list

        trace("HYDRATOR", session_id,
              f"batch lookup for {len(missing_ids)} doctor ID(s): {missing_ids}")

        id_to_name: dict[str, str] = {}
        try:
            raw = await self._tools.lookup_doctors_by_ids(missing_ids)
            if isinstance(raw, dict):
                id_to_name = {k: v for k, v in raw.items() if v}
                trace("HYDRATOR", session_id,
                      f"resolved {len(id_to_name)}/{len(missing_ids)} name(s): {id_to_name}")
            else:
                trace("HYDRATOR", session_id,
                      f"unexpected lookup response type: {type(raw).__name__} — using fallbacks")
        except Exception as exc:
            trace("HYDRATOR", session_id, f"batch lookup ERROR: {exc} — using fallbacks")

        for appt in appointment_list:
            doc_id = appt.get("doctor_id", "")
            if not doc_id:
                continue
            if appt.get("doctor_name") and appt["doctor_name"] != doc_id:
                continue
            resolved = id_to_name.get(doc_id)
            appt["doctor_name"] = resolved or _fallback_name(doc_id)
            trace("HYDRATOR", session_id,
                  f"doctor_id={doc_id!r} → {appt['doctor_name']!r} "
                  f"({'resolved' if resolved else 'fallback'})")

        return appointment_list
