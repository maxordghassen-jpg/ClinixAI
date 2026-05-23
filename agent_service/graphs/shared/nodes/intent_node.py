import json
import re
from typing import Optional

from groq import AsyncGroq
from pydantic import BaseModel

from app.config.settings import settings
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

client = AsyncGroq(api_key=settings.GROQ_API_KEY)

# Intents that represent an active, in-progress workflow.
# If the LLM returns "none" but the current memory holds one of these,
# the existing intent is preserved — a vague mid-workflow reply ("ok",
# "sure", "sounds good") must not derail an active booking or search.
ACTIVE_WORKFLOW_INTENTS = {
    "booking",
    "doctor_search",
    "select_doctor",
    "cancel_appointment",
    "reschedule_appointment",
    "view_appointments",
    "geo_search",
}

# Steps that belong to an active reschedule workflow.
# Date/time input during these steps must be mapped to new_date/new_time,
# and any stray booking/view_appointments classification overridden.
_RESCHEDULE_ACTIVE_STEPS: frozenset[str] = frozenset({
    "confirming_reschedule",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "awaiting_reschedule_slot_selection",
    "ready_to_reschedule",
})

# Steps that indicate an active booking workflow where asking about
# "available slots / times" should stay inside the booking flow.
_BOOKING_ACTIVE_STEPS: frozenset[str] = frozenset({
    "awaiting_specialty",
    "searching_doctors",
    "selecting_doctor",
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",
    "awaiting_recovery_choice",
    "ready_to_book",
    "selecting_place",
})

# Keywords (any language) that signal the user is asking about slot/time
# availability — not requesting a list of their booked appointments.
_AVAILABILITY_KEYWORDS: frozenset[str] = frozenset({
    # English
    "available", "availability", "slots", "slot", "times", "time",
    "free", "opening", "openings", "schedule", "options",
    # French
    "disponible", "disponibles", "disponibilité",
    "créneaux", "créneau", "horaires", "libre", "libres", "plages",
    # Arabic
    "متاح", "متاحة", "مواعيد", "أوقات", "وقت", "فراغ",
})

SPECIALTY_NORMALIZATION = {
    # Cardiology
    "cardiologist": "cardiologue",
    "heart doctor": "cardiologue",
    # Dermatology
    "dermatologist": "dermatologue",
    "skin doctor": "dermatologue",
    "skin specialist": "dermatologue",
    # Dental
    "dentist": "dentiste",
    "tooth doctor": "dentiste",
    # Neurology
    "neurologist": "neurologue",
    "brain doctor": "neurologue",
}


# Vocabulary that unambiguously signals a reschedule intent.
# Used in the safety-net override when the LLM returns select_appointment for
# a combined "reschedule the Nth appointment" message.
_RESCHEDULE_KEYWORDS: frozenset[str] = frozenset({
    # English
    "reschedule",
    # French
    "reporter", "reprogrammer", "déplacer",
    # Arabic
    "تأجيل",
})


class IntentSchema(BaseModel):
    intent: str
    specialty: Optional[str] = None
    doctor_name: Optional[str] = None
    place_type: Optional[str] = None
    date: Optional[str] = None
    new_date: Optional[str] = None          # for reschedule: the new target date
    new_time: Optional[str] = None          # for reschedule: the new target time
    time: Optional[str] = None
    selected_doctor_index: Optional[int] = None
    selected_appointment_index: Optional[int] = None  # for cancel/reschedule selection
    appointment_period: Optional[str] = None  # "today" | "week" | "next_week" | "all"
    reminder_hours: Optional[int] = None    # for set_reminder
    query: Optional[str] = None
    language: Optional[str] = None


class IntentNode:

    async def run(self, state: AgentState) -> AgentState:

        trace("INTENT", state.session_id,
              f"detecting intent for message: {state.message!r}")

        prompt = f"""
You are an AI medical assistant.

Your job:
- detect intent
- extract entities
- detect language

Return ONLY valid JSON with no markdown, no explanation.

Allowed intents:
- doctor_search          (find a doctor by specialty)
- booking                (book an appointment with a doctor)
- cancel_appointment     (cancel an existing appointment)
- reschedule_appointment (move an existing appointment to a new date/time)
- view_appointments      (list the patient's upcoming or recent appointments)
- set_reminder           (set a notification preference before appointments)
- geo_search             (find nearby clinics, pharmacies, hospitals)
- select_doctor          (patient is choosing a doctor from a list, e.g. "1" or "2")
- select_appointment     (patient is choosing an appointment from a list, e.g. "1" or "2")
- none

Languages: english | french | arabic

Entity fields (include only what applies):
  specialty               - normalized specialty name
  date                    - date string (as said by user)
  time                    - time string (as said by user)
  new_date                - new date for reschedule
  new_time                - new time for reschedule
  selected_doctor_index   - integer (1-based) when intent=select_doctor
  selected_appointment_index - integer (1-based) when intent=select_appointment
  appointment_period      - "today" | "week" | "next_week" | "all" for view_appointments
  reminder_hours          - integer for set_reminder (e.g. 2 for "2 hours before")
  query                   - search query for geo_search

Examples:

User: I need a cardiologist
Output: {{"intent":"doctor_search","specialty":"cardiologist","language":"english"}}

User: Book with Dr. Smith on Friday at 3 pm
Output: {{"intent":"booking","date":"Friday","time":"3 pm","language":"english"}}

User: What appointments do I have this week?
Output: {{"intent":"view_appointments","appointment_period":"week","language":"english"}}

User: Cancel my appointment
Output: {{"intent":"cancel_appointment","language":"english"}}

User: Cancel the second one
Output: {{"intent":"select_appointment","selected_appointment_index":2,"language":"english"}}

User: Reschedule the first appointment
Output: {{"intent":"reschedule_appointment","selected_appointment_index":1,"language":"english"}}

User: Cancel appointment number 2
Output: {{"intent":"cancel_appointment","selected_appointment_index":2,"language":"english"}}

User: Reschedule my second appointment
Output: {{"intent":"reschedule_appointment","selected_appointment_index":2,"language":"english"}}

User: Reschedule tomorrow's appointment to next Monday at 10am
Output: {{"intent":"reschedule_appointment","new_date":"next Monday","new_time":"10am","language":"english"}}

User: Remind me 2 hours before my appointments
Output: {{"intent":"set_reminder","reminder_hours":2,"language":"english"}}

User: 1
Output: {{"intent":"select_doctor","selected_doctor_index":1,"language":"english"}}

User: Je cherche une pharmacie proche
Output: {{"intent":"geo_search","query":"pharmacy","language":"french"}}

User: أريد إلغاء موعدي
Output: {{"intent":"cancel_appointment","language":"arabic"}}

Current memory context:
  intent:    {state.memory.get("intent")}
  step:      {state.memory.get("step")}
  specialty: {state.memory.get("specialty")}
  doctor_id: {state.memory.get("doctor_id")}
  date:      {state.memory.get("date")}
  time:      {state.memory.get("time")}
  new_date:  {state.memory.get("new_date")}
  new_time:  {state.memory.get("new_time")}

User message: {state.message}
"""

        try:
            response = await client.chat.completions.create(
                model=settings.MODEL_NAME,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an intent extraction AI for a multilingual medical assistant.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0,
            )

            content = response.choices[0].message.content
            trace("INTENT", state.session_id, f"LLM raw response: {content!r}")

            cleaned = re.sub(r"```json|```", "", content).strip()
            parsed = json.loads(cleaned)
            validated = IntentSchema(**parsed)
            extracted = validated.model_dump(exclude_none=True)

            # Specialty normalization
            specialty = extracted.get("specialty")
            if specialty in SPECIALTY_NORMALIZATION:
                extracted["specialty"] = SPECIALTY_NORMALIZATION[specialty]
                trace("INTENT", state.session_id,
                      f"specialty normalized: {specialty!r} → {extracted['specialty']!r}")

            # Active-workflow guard: if LLM returns "none" but an active workflow
            # is running, preserve the existing intent so vague replies ("ok",
            # "yes", "sure") don't kill an in-progress booking or cancellation.
            new_intent = extracted.get("intent")
            existing_intent = state.memory.get("intent")

            if new_intent in (None, "none") and existing_intent in ACTIVE_WORKFLOW_INTENTS:
                extracted.pop("intent", None)
                trace("INTENT", state.session_id,
                      f"active-workflow guard: kept existing intent={existing_intent!r} "
                      f"(LLM returned {new_intent!r})")

            # Contextual intent override (Bug 2): "show me available slots / times"
            # inside an active booking flow must stay as booking, not be treated as
            # a request to view the patient's booked appointment list.
            # The LLM has no awareness of step context and reliably misclassifies
            # availability queries as view_appointments when no appointment is yet booked.
            new_intent = extracted.get("intent")
            current_step = state.memory.get("step")
            if (
                new_intent == "view_appointments"
                and current_step in _BOOKING_ACTIVE_STEPS
                and any(kw in state.message.lower() for kw in _AVAILABILITY_KEYWORDS)
            ):
                extracted["intent"] = "booking"
                trace("INTENT", state.session_id,
                      f"contextual override: view_appointments → booking "
                      f"(step={current_step!r}, availability keyword matched)")

            # Safety-net override: "reschedule the first/second/… appointment" in a
            # single message.  The LLM has no combined-intent example and collapses
            # action+selection into select_appointment, losing the reschedule ownership.
            # Detect explicit reschedule vocabulary and promote the intent so WorkflowNode
            # sets pending_action="reschedule" before selecting_appointment runs.
            new_intent = extracted.get("intent")
            if new_intent == "select_appointment":
                msg_lower = state.message.lower()
                if any(kw in msg_lower for kw in _RESCHEDULE_KEYWORDS):
                    extracted["intent"] = "reschedule_appointment"
                    trace("INTENT", state.session_id,
                          f"safety-net override: select_appointment → reschedule_appointment "
                          f"(reschedule keyword in message)")

            # Contextual override: any booking/view intent during an active reschedule
            # flow must stay as reschedule_appointment.  The LLM sees a date/time reply
            # ("next Monday", "10am") and may classify it as booking without step context.
            new_intent = extracted.get("intent")
            if (
                new_intent in ("booking", "view_appointments")
                and current_step in _RESCHEDULE_ACTIVE_STEPS
            ):
                extracted["intent"] = "reschedule_appointment"
                trace("INTENT", state.session_id,
                      f"contextual override: {new_intent!r} → reschedule_appointment "
                      f"(step={current_step!r})")

            # Field remapping: when inside a reschedule step the LLM may populate
            # date/time instead of new_date/new_time.  Move them to the correct keys
            # so ActionNode's awaiting_reschedule_date/time handlers find them.
            if current_step in _RESCHEDULE_ACTIVE_STEPS:
                if extracted.get("date") and not extracted.get("new_date"):
                    extracted["new_date"] = extracted.pop("date")
                    trace("INTENT", state.session_id,
                          f"field remap: date → new_date={extracted['new_date']!r} "
                          f"(step={current_step!r})")
                if extracted.get("time") and not extracted.get("new_time"):
                    extracted["new_time"] = extracted.pop("time")
                    trace("INTENT", state.session_id,
                          f"field remap: time → new_time={extracted['new_time']!r} "
                          f"(step={current_step!r})")

            state.memory.update(extracted)

            # Record which keys were extracted this turn so ActionNode can
            # distinguish "fresh from current message" vs "loaded from Redis cache".
            # This is consumed by clear_stale_scheduling and never persisted.
            state.extracted_this_turn = set(extracted.keys())

            trace("INTENT", state.session_id,
                  f"merged into memory: {extracted} | "
                  f"intent={state.memory.get('intent')} "
                  f"step={state.memory.get('step')} "
                  f"date={state.memory.get('date')} "
                  f"time={state.memory.get('time')} | "
                  f"extracted_this_turn={sorted(state.extracted_this_turn)}")

        except Exception as exc:
            # On any parse / validation failure, preserve existing memory.
            # The downstream nodes continue from the step already in Redis.
            trace("INTENT", state.session_id,
                  f"PARSE ERROR — memory preserved | error: {exc}")

        return state
