from typing import Any

from graphs.doctor.tools.appointments.intents import is_schedule_view
from graphs.shared.formatting import (
    appointment_date_context,
    appointment_header,
    completed_message,
    doctor_display_name,
    empty_message,
    format_daily_schedule,
    format_date,
    format_status,
    format_weekday,
    normalize_language,
    patient_display_name,
)
from graphs.shared.schemas import AgentState


class ResponseGenerator:
    async def run(self, state: AgentState) -> AgentState:
        language = normalize_language(state.intent.language if state.intent else None)
        result = state.tool_result
        if isinstance(result, list):
            state.response = self._format_list(result, state, language)
        elif isinstance(result, dict):
            state.response = self._format_dict(result, state, language)
        else:
            state.response = completed_message(language)
        return state

    def _format_list(
        self,
        items: list[dict[str, Any]],
        state: AgentState,
        language: str,
    ) -> str:
        if not items:
            return empty_message(language)
        if state.intent and state.intent.tool == "appointments":
            action = state.intent.action

            # Compact calendar view for daily/weekly schedule actions
            if is_schedule_view(action):
                context = appointment_date_context(items, action, language)
                return format_daily_schedule(items, language, context)

            context = appointment_date_context(items, action, language)
            lines = [appointment_header(len(items), context, language)]
            for item in items:
                lines.append(self._format_appointment_line(item, state, language))
            return "\n".join(lines)

        lines = [self._availability_header(len(items), language)]
        for item in items:
            lines.append(self._format_slot_line(item, language))
        return "\n".join(lines)

    def _format_dict(
        self,
        item: dict[str, Any],
        state: AgentState,
        language: str,
    ) -> str:
        if "message" in item:
            return item["message"]
        if "results" in item:
            return self._format_medical_places(item, language)
        if "status" in item and "time" in item:
            return self._format_appointment_summary(item, language)
        if "slots" in item:
            return self._format_availability_summary(item, language)
        return completed_message(language)

    def _format_appointment_line(
        self,
        item: dict[str, Any],
        state: AgentState,
        language: str,
    ) -> str:
        doctor_or_patient = (
            doctor_display_name(item)
            if state.role == "patient"
            else patient_display_name(item)
        )

        date_value = format_date(item.get("date"), language)
        time_value = item.get("time", "--:--")
        status = format_status(item.get("status"), language)

        status_icons = {
            "confirmed": "✅",
            "pending": "🟡",
            "rejected": "❌",
            "cancelled": "🚫",
        }

        raw_status = item.get("status", "pending")
        icon = status_icons.get(raw_status, "ℹ️")

        lines = [
            f"\n• {doctor_or_patient}",
            f"  📅 {date_value}",
            f"  🕒 {time_value}",
            f"  {icon} {status}",
        ]

        return "\n".join(lines)

    def _format_slot_line(self, item: dict[str, Any], language: str) -> str:
        start = item.get("start", "--:--")
        end = item.get("end", "--:--")
        status = format_status(item.get("status", "available"), language)
        return f"• {start} — {end} — {status}"

    def _format_appointment_summary(self, item: dict[str, Any], language: str) -> str:
        status = format_status(item.get("status"), language)
        date_label = format_date(item.get("date"), language)
        time_value = item.get("time", "--:--")

        if language == "fr":
            when = f" le {date_label} à {time_value}" if date_label else f" à {time_value}"
            return f"Le rendez-vous est {status}{when}."
        if language == "ar":
            when = f" في {date_label} الساعة {time_value}" if date_label else f" الساعة {time_value}"
            return f"الموعد {status}{when}."
        when = f" on {date_label} at {time_value}" if date_label else f" at {time_value}"
        return f"The appointment is {status}{when}."

    def _format_availability_summary(self, item: dict[str, Any], language: str) -> str:
        day = item.get("day")
        count = len(item.get("slots", []))
        if language == "fr":
            return f"La disponibilité pour {day} contient {count} créneaux."
        if language == "ar":
            return f"تحتوي المواعيد المتاحة في {day} على {count} فترات زمنية."
        return f"Availability for {day} has {count} slots."

    def _availability_header(self, count: int, language: str) -> str:
        if language == "fr":
            return f"Vous avez {count} créneaux disponibles :"
        if language == "ar":
            return f"لديك {count} فترات متاحة:"
        return f"You have {count} available slots:"

    def _format_medical_places(self, item: dict[str, Any], language: str) -> str:
        results = item.get("results", [])
        count = item.get("results_count", len(results))

        if not results:
            return empty_message(language)

        if language == "fr":
            header = f"J’ai trouvé {count} résultats :"
            open_text = "🟢 Ouvert"
            closed_text = "🔴 Fermé"

        elif language == "ar":
            header = f"وجدت {count} نتائج:"
            open_text = "🟢 مفتوح"
            closed_text = "🔴 مغلق"

        else:
            header = f"I found {count} results:"
            open_text = "🟢 Open"
            closed_text = "🔴 Closed"

        lines = [header]

        for place in results[:5]:
            name = place.get("name", "Unknown place")
            address = place.get("address", "Unknown address")
            rating = place.get("rating")
            phone = place.get("phone_number")
            is_open = place.get("is_open_now")

            lines.append(f"\n• {name}")

            lines.append(f"  📍 {address}")

            if rating:
                lines.append(f"  ⭐ {rating}/5")

            if phone:
                lines.append(f"  📞 {phone}")

            if is_open is not None:
                if is_open:
                    lines.append(f"  {open_text}")
                else:
                    lines.append(f"  {closed_text}")

        return "\n".join(lines)
    def _place_detail(self, place: dict[str, Any]) -> str:
        parts = []
        if place.get("distance_text"):
            parts.append(place["distance_text"])
        if place.get("governorate"):
            parts.append(place["governorate"])
        if place.get("rating"):
            parts.append(f"{place['rating']}/5")
        return f" — {' — '.join(parts)}" if parts else ""
