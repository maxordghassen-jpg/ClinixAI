from graphs.patient.shared.prompts import PATIENT_INTENT_PROMPT
from graphs.patient.tools.appointments.prompts import PATIENT_APPOINTMENTS_PROMPT
from graphs.patient.tools.availability.prompts import PATIENT_AVAILABILITY_PROMPT
from graphs.patient.tools.medical_places.prompts import MEDICAL_PLACES_PROMPT
from graphs.shared.llm_router import LLMRouter
from graphs.shared.schemas import AgentState, IntentResult


class IntentDetector:
    def __init__(self):
        self.llm = LLMRouter()

    async def run(self, state: AgentState) -> AgentState:
        result = await self.llm.complete_json(
            (
                f"{PATIENT_INTENT_PROMPT}\n"
                f"{PATIENT_APPOINTMENTS_PROMPT}\n"
                f"{PATIENT_AVAILABILITY_PROMPT}\n"
                f"{MEDICAL_PLACES_PROMPT}"
            ),
            state.message,
        )
        state.intent = IntentResult(**result) if result else self._fallback(state.message)
        return state

    def _fallback(self, message: str) -> IntentResult:
        text = message.lower()
        entities = self._fallback_entities(text)

        if any(word in text for word in ["pharmacy", "pharmacie", "hospital", "hopital", "clinic", "clinique"]):
            if "pharmacy" in text or "pharmacie" in text:
                action = "search_nearby_pharmacies" if self._is_nearby(text) else "search_by_city"
                entities.setdefault("category", "pharmacies")
            elif "hospital" in text or "hopital" in text:
                action = "search_nearby_hospitals" if self._is_nearby(text) else "search_by_city"
                entities.setdefault("category", "hospitals")
            else:
                action = "search_nearby_clinics" if self._is_nearby(text) else "search_by_city"
                entities.setdefault("category", "clinics")
            return IntentResult(tool="medical_places", action=action, confidence=0.45, entities=entities)

        if any(word in text for word in ["cardiologist", "cardiologue", "dentist", "dentiste", "doctor", "medecin"]):
            entities.setdefault("specialty", self._extract_specialty(text))
            entities.setdefault("category", "doctors")
            return IntentResult(
                tool="medical_places",
                action="search_doctors_by_specialty",
                confidence=0.45,
                entities=entities,
            )

        if any(word in text for word in ["available", "availability", "slot", "slots", "disponible", "creneau"]):
            action = "view_available_slots"
            if "tomorrow" in text or "demain" in text:
                action = "view_tomorrow_availability"
            elif "today" in text or "aujourd" in text:
                action = "view_today_availability"
            return IntentResult(tool="availability", action=action, confidence=0.45, entities=entities)

        if any(word in text for word in ["book", "prendre", "reserver"]):
            return IntentResult(tool="appointments", action="book_appointment", confidence=0.4, entities=entities)
        if any(word in text for word in ["cancel", "annul"]):
            return IntentResult(tool="appointments", action="cancel_appointment", confidence=0.4, entities=entities)
        if any(word in text for word in ["reschedule", "reporter", "changer"]):
            return IntentResult(tool="appointments", action="reschedule_appointment", confidence=0.4, entities=entities)
        if any(word in text for word in ["rdv", "rendez", "appointment"]):
            action = "view_week_appointments" if "week" in text or "semaine" in text else "view_today_appointments"
            return IntentResult(tool="appointments", action=action, confidence=0.4, entities=entities)
        return IntentResult()

    def _fallback_entities(self, text: str) -> dict:
        entities = {}
        for city in ["tunis", "sfax", "sousse", "ariana", "nabeul", "bizerte"]:
            if city in text:
                entities["city"] = city.title()
                entities["governorate"] = city.title()
                break
        return entities

    def _extract_specialty(self, text: str) -> str | None:
        specialty_map = {
            "cardiologist": "cardiologie",
            "cardiologue": "cardiologie",
            "dentist": "dentiste",
            "dentiste": "dentiste",
        }
        for key, value in specialty_map.items():
            if key in text:
                return value
        return None

    def _is_nearby(self, text: str) -> bool:
        return any(word in text for word in ["near", "nearby", "nearest", "proche", "pres", "près"])
