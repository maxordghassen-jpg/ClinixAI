from graphs.doctor.shared.prompts import DOCTOR_INTENT_PROMPT
from graphs.doctor.tools.appointments.prompts import APPOINTMENTS_PROMPT
from graphs.doctor.tools.availability.prompts import AVAILABILITY_PROMPT
from graphs.doctor.tools.reports.prompts import REPORTS_PROMPT
from graphs.shared.llm_router import LLMRouter
from graphs.shared.schemas import AgentState, IntentResult


class IntentDetector:
    def __init__(self):
        self.llm = LLMRouter()

    async def run(self, state: AgentState) -> AgentState:
        prompt = f"{DOCTOR_INTENT_PROMPT}\n{APPOINTMENTS_PROMPT}\n{AVAILABILITY_PROMPT}\n{REPORTS_PROMPT}"
        result = await self.llm.complete_json(prompt, state.message)
        state.intent = IntentResult(**result) if result else self._fallback(state.message)
        return state

    def _fallback(self, message: str) -> IntentResult:
        text = message.lower()
        # Exception / closure keywords — check before generic availability
        if any(w in text for w in ["vacation", "congé", "conge", "fermeture", "closure", "unavailable"]):
            if any(w in text for w in ["to ", "au ", "until", "jusqu", "-"]):
                return IntentResult(tool="availability", action="vacation_mode", confidence=0.4)
            return IntentResult(tool="availability", action="block_day", confidence=0.4)
        if any(w in text for w in ["override", "only", "seulement", "uniquement"]):
            return IntentResult(tool="availability", action="override_hours", confidence=0.4)
        if any(w in text for w in ["exceptions", "blocages", "fermetures"]):
            return IntentResult(tool="availability", action="view_exceptions", confidence=0.4)

        if any(word in text for word in ["dispon", "availability", "slot", "créneau", "creneau"]):
            action = "view_available_slots"
            if "block" in text or "bloqu" in text:
                action = "block_availability"
            if "unblock" in text or "débloqu" in text or "debloqu" in text:
                action = "unblock_availability"
            return IntentResult(tool="availability", action=action, confidence=0.4)
        if any(word in text for word in [
            "rdv", "rendez", "appointment", "موعد", "schedule", "planning", "agenda"
        ]):
            action = "view_appointments"
            if any(w in text for w in ["schedule", "planning", "agenda", "calendar"]):
                action = "daily_schedule"
                if "week" in text or "semaine" in text:
                    action = "weekly_schedule"
            elif "today" in text or "aujourd" in text:
                action = "view_today_appointments"
            elif "tomorrow" in text or "demain" in text:
                action = "view_tomorrow_appointments"
            elif "week" in text or "semaine" in text:
                action = "view_week_appointments"
            elif "confirm" in text or "accept" in text:
                action = "confirm_appointment"
            elif "reject" in text or "refus" in text:
                action = "reject_appointment"
            elif any(w in text for w in ["cancel", "annul"]):
                action = "cancel_appointment"
            elif any(w in text for w in ["reschedule", "reporter", "déplacer", "deplac"]):
                action = "reschedule_appointment"
            return IntentResult(tool="appointments", action=action, confidence=0.4)
        return IntentResult()
