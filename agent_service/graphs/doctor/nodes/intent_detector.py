from graphs.doctor.shared.prompts import DOCTOR_INTENT_PROMPT
from graphs.doctor.tools.appointments.prompts import APPOINTMENTS_PROMPT
from graphs.doctor.tools.availability.prompts import AVAILABILITY_PROMPT
from graphs.shared.llm_router import LLMRouter
from graphs.shared.schemas import AgentState, IntentResult


class IntentDetector:
    def __init__(self):
        self.llm = LLMRouter()

    async def run(self, state: AgentState) -> AgentState:
        prompt = f"{DOCTOR_INTENT_PROMPT}\n{APPOINTMENTS_PROMPT}\n{AVAILABILITY_PROMPT}"
        result = await self.llm.complete_json(prompt, state.message)
        state.intent = IntentResult(**result) if result else self._fallback(state.message)
        return state

    def _fallback(self, message: str) -> IntentResult:
        text = message.lower()
        if any(word in text for word in ["dispon", "availability", "slot", "créneau", "creneau"]):
            action = "view_available_slots"
            if "block" in text or "bloqu" in text:
                action = "block_availability"
            if "unblock" in text or "débloqu" in text or "debloqu" in text:
                action = "unblock_availability"
            return IntentResult(tool="availability", action=action, confidence=0.4)
        if any(word in text for word in ["rdv", "rendez", "appointment", "موعد"]):
            action = "view_appointments"
            if "today" in text or "aujourd" in text:
                action = "view_today_appointments"
            elif "tomorrow" in text or "demain" in text:
                action = "view_tomorrow_appointments"
            elif "week" in text or "semaine" in text:
                action = "view_week_appointments"
            elif "confirm" in text or "accept" in text:
                action = "confirm_appointment"
            elif "reject" in text or "refus" in text:
                action = "reject_appointment"
            elif "cancel" in text or "annul" in text:
                action = "cancel_appointment"
            return IntentResult(tool="appointments", action=action, confidence=0.4)
        return IntentResult()
