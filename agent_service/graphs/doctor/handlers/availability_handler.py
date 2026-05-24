from typing import Any

from graphs.doctor.mcp.tool_caller import ToolCaller
from graphs.shared.normalizers.date_normalizer import DateNormalizer
from graphs.shared.scheduling_engine.recurrence_engine import current_french_day, resolve_day
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace


class AvailabilityHandler:
    def __init__(self):
        self.tool_caller = ToolCaller()

    async def handle(self, state: AgentState) -> Any:
        intent = state.intent
        action = intent.action if intent else "view_availability"
        entities = intent.entities if intent else {}

        doctor_id = state.doctor_id or state.memory.get("doctor_id")
        if not doctor_id:
            trace("DOCTOR-AVAIL", state.session_id, "ERROR: doctor_id is None")
            return {"message": "Doctor identity could not be determined. Please re-authenticate."}

        # ── Template view actions ──────────────────────────────────────────────

        if action in {"view_available_slots", "view_today_availability", "view_tomorrow_availability"}:
            day = resolve_day(action, entities)
            return await self.tool_caller.get_availability(
                f"/availability/{doctor_id}/{day}/free-slots"
            )

        if action in {"view_availability", "view_week_availability", "view_next_week_availability"}:
            return await self.tool_caller.get_availability(f"/availability/{doctor_id}")

        # ── Template mutation actions ──────────────────────────────────────────

        if action == "create_availability":
            day = resolve_day(action, entities)
            return await self.tool_caller.post_availability(
                "/availability",
                {
                    "doctor_id": doctor_id,
                    "day": day,
                    "slots": entities.get("slots", []),
                },
            )

        if action == "update_availability":
            avail_id = entities.get("availability_id")
            if not avail_id:
                return {"message": "Please specify the availability template ID to update."}
            return await self.tool_caller.post_availability(
                f"/availability/{avail_id}",
                {"slots": entities.get("slots", [])},
            )

        if action in {"block_availability", "unblock_availability"}:
            endpoint = "block" if action == "block_availability" else "unblock"
            day = resolve_day(action, entities)
            start = entities.get("time") or entities.get("start")
            if not start:
                return {"message": "Please specify the time slot to block/unblock (e.g. 10:00)."}
            return await self.tool_caller.post_availability(
                f"/availability/slots/{endpoint}",
                {"doctor_id": doctor_id, "day": day, "start": start},
            )

        if action == "delete_availability":
            avail_id = entities.get("availability_id")
            if not avail_id:
                return {"message": "Please specify the availability template ID to delete."}
            return await self.tool_caller.delete_availability(f"/availability/{avail_id}")

        # ── Exception actions ──────────────────────────────────────────────────

        if action == "block_day":
            iso_date = DateNormalizer.normalize_safe(entities.get("date"))
            if not iso_date:
                return {"message": "Please specify the date to block (e.g. 2026-05-30)."}
            return await self.tool_caller.post_exception({
                "doctor_id": doctor_id,
                "date":      iso_date,
                "type":      "closure",
                "reason":    entities.get("reason", "blocked"),
            })

        if action == "vacation_mode":
            start_iso = DateNormalizer.normalize_safe(
                entities.get("start_date") or entities.get("date")
            )
            end_iso = DateNormalizer.normalize_safe(entities.get("end_date"))
            if not start_iso:
                return {"message": "Please specify the vacation start date."}
            if not end_iso:
                return {"message": "Please specify the vacation end date."}
            return await self.tool_caller.post_exception({
                "doctor_id": doctor_id,
                "date":      start_iso,
                "end_date":  end_iso,
                "type":      "vacation",
                "reason":    entities.get("reason", "vacation"),
            })

        if action == "override_hours":
            iso_date = DateNormalizer.normalize_safe(entities.get("date"))
            if not iso_date:
                return {"message": "Please specify the date for the schedule override."}
            override_slots = entities.get("slots") or entities.get("ranges", [])
            if not override_slots:
                return {"message": "Please specify the override hours (e.g. [{\"start\": \"10:00\", \"end\": \"14:00\"}])."}
            return await self.tool_caller.post_exception({
                "doctor_id":       doctor_id,
                "date":            iso_date,
                "type":            "override",
                "override_ranges": override_slots,
                "reason":          entities.get("reason"),
            })

        if action == "view_exceptions":
            return await self.tool_caller.get_exceptions(doctor_id)

        if action == "delete_exception":
            exc_id = entities.get("exception_id")
            if not exc_id:
                return {"message": "Please specify the exception ID to delete."}
            return await self.tool_caller.delete_exception(exc_id)

        trace("DOCTOR-AVAIL", state.session_id, f"unsupported action: {action!r}")
        return {"message": f"Unsupported availability action: {action}"}
