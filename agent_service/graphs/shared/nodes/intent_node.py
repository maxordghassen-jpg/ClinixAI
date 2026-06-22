import json
import re
import time
from typing import Optional

import openai
from pydantic import BaseModel

from app.config.settings import settings
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace

client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

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
    "check_availability",
    "preconsultation",
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

# Steps that belong to an active preconsultation questionnaire.
# Any answer the patient gives here is a symptom response, not a new intent.
_PRECONSULTATION_ACTIVE_STEPS: frozenset[str] = frozenset({
    "collecting_chief_complaint",
    "collecting_duration",
    "collecting_severity",
    "collecting_associated",
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
})

# Result fields of a COMPLETED preconsultation questionnaire. If a resumed
# snapshot's own step is NOT one of _PRECONSULTATION_ACTIVE_STEPS (i.e. it's
# a booking/reschedule/cancel step, meaning the questionnaire already
# finished for that prior attempt), these must not be restored into a new
# booking — otherwise the new booking inherits preconsultation_done=True
# and skips its own questionnaire.
_STALE_PRECONSULT_FIELDS: frozenset[str] = frozenset({
    "preconsultation_done",
    "symptom_chief_complaint",
    "symptom_duration",
    "symptom_severity",
    "symptom_associated",
    "recommended_specialty",
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
    "awaiting_availability_recovery",
    "ready_to_book",
    "selecting_place",
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
})

# Booking-recovery sub-steps: the patient is expected to reply with a bare
# date/time/slot choice (e.g. after a 409 "no availability" conflict and
# choosing "try another date"). The LLM has no step context here and may
# misclassify a bare date/time phrase as reschedule_appointment /
# cancel_appointment / view_appointments.
_BOOKING_RECOVERY_STEPS: frozenset[str] = frozenset({
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",
    "awaiting_recovery_choice",
    "awaiting_availability_recovery",
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
    # Pediatrics
    "pediatrician": "pédiatre",
    "pediatric doctor": "pédiatre",
    "child doctor": "pédiatre",
    "pediatrics": "pédiatre",
    "pédiatre": "pédiatre",
    "pédiatrie": "pédiatre",
    "طبيب أطفال": "pédiatre",
    "طب أطفال": "pédiatre",
    "أطفال": "pédiatre",
    "پدیاتری": "pédiatre",
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


def _is_language_neutral(message: str) -> bool:
    """Return True when the message carries no reliable language signal.

    The LLM returns language="english" for purely numeric or symbolic
    inputs ("1", "11:00", "2026-06-20") regardless of the established
    session language. These inputs are language-neutral — they should
    never cause a language switch.
    """
    stripped = message.strip()
    if not stripped:
        return True
    # Pure integer (menu selection, slot number, severity score, etc.)
    if re.fullmatch(r"\d+", stripped):
        return True
    # Time: HH:MM, H:MM, HHhMM, HH:MM:SS
    if re.fullmatch(r"\d{1,2}[h:]\d{2}(:\d{2})?", stripped, re.IGNORECASE):
        return True
    # Numeric date: YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY, DD.MM.YYYY
    if re.fullmatch(r"\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}", stripped):
        return True
    return False

# Affirmative words recognised at step=preconsultation_complete.
# When the patient answers "yes" to the specialist recommendation question,
# the LLM typically returns intent=none (plain affirmative has no extractable
# entities). The ACTIVE_WORKFLOW_INTENTS guard then preserves the existing
# intent=preconsultation, causing WorkflowNode to loop back into the summary.
# Detecting these words and forcing intent=booking breaks that loop.
_POSTCONSULT_AFFIRMATIVES: frozenset[str] = frozenset({
    # English
    "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "alright", "please",
    "find", "search", "book", "go",
    # French
    "oui", "ouais", "d'accord", "accord", "bien", "sûr", "volontiers",
    "chercher", "cherche", "réserver", "réserve",
    # Arabic
    "نعم", "أجل", "حسنا", "تمام", "موافق", "تفضل", "ابحث",
})


class IntentSchema(BaseModel):
    intent: str
    specialty: Optional[str] = None
    doctor_id: Optional[str] = None         # explicit doctor ID from message or UI context
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
    urgency: Optional[str] = None           # "high" when user signals urgency


class IntentNode:

    async def run(self, state: AgentState) -> AgentState:

        trace("INTENT", state.session_id,
              f"detecting intent for message: {state.message!r}")

        # When the patient is mid-questionnaire, hide stale booking fields from
        # the LLM context.  The LLM reliably echoes whatever it sees in memory
        # (doctor_id, date, time) into its JSON output, causing duration answers
        # like "1 day" to be misclassified as booking intents with a date entity.
        _in_preconsult = state.memory.get("step") in _PRECONSULTATION_ACTIVE_STEPS
        _ctx_doctor_id = None if _in_preconsult else state.memory.get("doctor_id")
        _ctx_date      = None if _in_preconsult else state.memory.get("date")
        _ctx_time      = None if _in_preconsult else state.memory.get("time")

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
- check_availability     (check if a SPECIFIC named doctor has free slots on a date)
- cancel_appointment     (cancel an existing appointment)
- reschedule_appointment (move an existing appointment to a new date/time)
- view_appointments      (list the patient's upcoming or recent appointments)
- set_reminder           (set a notification preference before appointments)
- geo_search             (find nearby clinics, pharmacies, hospitals, or doctors by LOCATION — "near me", "nearby", "close to me")
- select_doctor          (patient is choosing a doctor from a list, e.g. "1" or "2")
- select_appointment     (patient is choosing an appointment from a list, e.g. "1" or "2")
- preconsultation        (patient wants to describe symptoms before a consultation)
- none

INTENT DISAMBIGUATION:
- check_availability: use ONLY when a specific doctor name is mentioned ("Is Dr. X available?",
  "Does Dr. Y have openings?", "Can I see Dr. Z on Friday?")
- booking: use when the patient wants to BOOK an appointment (not just check slots)
- doctor_search: use when looking for doctors BY SPECIALTY with no specific doctor named
- geo_search vs doctor_search: if the user mentions a LOCATION cue ("near me", "nearby",
  "close to me", "in my area"), use geo_search — even if a specialty is also mentioned.
  Include BOTH "query" (the specialty/place type) and "specialty" (the specialty name)
  in that case. If NO location cue is present, use doctor_search instead.

Languages: english | french | arabic

Entity fields (include only what applies):
  specialty               - normalized specialty name
  doctor_id               - explicit doctor ID if the user says "doctor ID: xxx" or "ID: xxx"
  doctor_name             - doctor's name if mentioned (e.g. "Dr. Smith")
  date                    - date string (as said by user)
  time                    - time string (as said by user)
  new_date                - new date for reschedule
  new_time                - new time for reschedule
  selected_doctor_index   - integer (1-based) when intent=select_doctor
  selected_appointment_index - integer (1-based) when intent=select_appointment
  appointment_period      - "today" | "week" | "next_week" | "all" for view_appointments
  reminder_hours          - integer for set_reminder (e.g. 2 for "2 hours before")
  query                   - search query for geo_search (place type, e.g. "pharmacy", or
                            specialty, e.g. "cardiologist")
  urgency                 - "high" ONLY when the user explicitly signals urgency with words like:
                            urgent, ASAP, as soon as possible, earliest, emergency, right away,
                            immediately, today, عاجل, d'urgence, dès que possible, maintenant

DOCTOR NAME EXTRACTION — always extract from these patterns:
  "Dr. Ahmed"      → doctor_name = "Ahmed"
  "Dr Ahmed"       → doctor_name = "Ahmed"
  "Doctor Ahmed"   → doctor_name = "Ahmed"
  "Dr. Sami Ben Ali" → doctor_name = "Sami Ben Ali"
  "Docteur Leila"  → doctor_name = "Leila"
  "الدكتور أحمد"  → doctor_name = "أحمد"
  Extract the NAME PART only — strip the "Dr." / "Doctor" / "Docteur" prefix.

IMPORTANT: When the user provides a doctor_id (e.g. "doctor ID: doc-003"), ALWAYS include it.
A booking with a known doctor_id does NOT need specialty — skip straight to date collection.

Examples:

User: I need a cardiologist
Output: {{"intent":"doctor_search","specialty":"cardiologist","language":"english"}}

User: Book with Dr. Smith on Friday at 3 pm
Output: {{"intent":"booking","doctor_name":"Dr. Smith","date":"Friday","time":"3 pm","language":"english"}}

User: Book an appointment with Dr. Leila Trabelsi, doctor ID: doc-003
Output: {{"intent":"booking","doctor_id":"doc-003","doctor_name":"Dr. Leila Trabelsi","language":"english"}}

User: Book with doctor ID doc-007 on Monday
Output: {{"intent":"booking","doctor_id":"doc-007","date":"Monday","language":"english"}}

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

User: Find a cardiologist near me
Output: {{"intent":"geo_search","query":"cardiologist","specialty":"cardiologist","language":"english"}}

User: أريد إلغاء موعدي
Output: {{"intent":"cancel_appointment","language":"arabic"}}

User: I need a cardiologist ASAP
Output: {{"intent":"booking","specialty":"cardiologist","urgency":"high","language":"english"}}

User: Book me the earliest available dentist today, it's urgent
Output: {{"intent":"booking","specialty":"dentiste","urgency":"high","language":"english"}}

User: J'ai besoin d'un médecin d'urgence
Output: {{"intent":"booking","urgency":"high","language":"french"}}

User: Is Dr. Ahmed available this Thursday?
Output: {{"intent":"check_availability","doctor_name":"Ahmed","date":"this Thursday","language":"english"}}

User: Can I see Dr. Sami tomorrow?
Output: {{"intent":"check_availability","doctor_name":"Sami","date":"tomorrow","language":"english"}}

User: Does Dr. Leila have openings Friday?
Output: {{"intent":"check_availability","doctor_name":"Leila","date":"Friday","language":"english"}}

User: Est-ce que le Dr. Hassan est disponible lundi ?
Output: {{"intent":"check_availability","doctor_name":"Hassan","date":"lundi","language":"french"}}

User: هل الدكتور أحمد متاح يوم الخميس؟
Output: {{"intent":"check_availability","doctor_name":"أحمد","date":"الخميس","language":"arabic"}}

User: Is Dr. HANNACHI free today?
Output: {{"intent":"check_availability","doctor_name":"HANNACHI","date":"today","language":"english"}}

User: I have a headache and want to describe my symptoms
Output: {{"intent":"preconsultation","language":"english"}}

User: Je veux décrire mes symptômes avant ma consultation
Output: {{"intent":"preconsultation","language":"french"}}

User: أريد وصف أعراضي قبل الاستشارة
Output: {{"intent":"preconsultation","language":"arabic"}}

Current memory context:
  intent:    {state.memory.get("intent")}
  step:      {state.memory.get("step")}
  specialty: {state.memory.get("specialty")}
  doctor_id: {_ctx_doctor_id}
  date:      {_ctx_date}
  time:      {_ctx_time}
  new_date:  {state.memory.get("new_date")}
  new_time:  {state.memory.get("new_time")}
{(chr(10) + state.memory_context + chr(10)) if state.memory_context else ""}
User message: {state.message}
"""

        try:
            response = await client.chat.completions.create(
                model=settings.MODEL_NAME,
                max_tokens=512,
                messages=[
                    {"role": "system", "content": "You are an intent extraction AI for a multilingual medical assistant."},
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
            if specialty is not None:
                trace("INTENT", state.session_id, f"Before normalization: specialty={specialty!r}")
                if specialty in SPECIALTY_NORMALIZATION:
                    extracted["specialty"] = SPECIALTY_NORMALIZATION[specialty]
                trace("INTENT", state.session_id, f"After normalization: specialty={extracted.get('specialty')!r}")

            # Explicit doctor_id override: a message carrying an explicit
            # doctor_id (e.g. "Book an appointment with X, doctor ID: <id>"
            # from the Find Doctors page) is an unambiguous request to book
            # that specific doctor. Force intent=booking so this signal can't
            # be lost to intent misclassification or to the active-workflow
            # guard below preserving a stale doctor_search/selecting_doctor
            # context.
            if extracted.get("doctor_id"):
                if extracted.get("intent") != "booking":
                    trace("INTENT", state.session_id,
                          f"explicit doctor_id override: intent "
                          f"{extracted.get('intent')!r} -> 'booking' "
                          f"(doctor_id={extracted['doctor_id']!r})")
                extracted["intent"] = "booking"

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

            # Contextual override (Bug 1 / CRIT-1): a stray reschedule/cancel/
            # view_appointments classification during booking-recovery date/time
            # sub-steps must not hijack an in-progress booking. Without an existing
            # selected_appointment_id there is nothing to reschedule, cancel, or
            # view — the message is almost certainly the patient's reply to "please
            # choose another date/time". Coerce back to booking and remap
            # new_date/new_time → date/time so the booking handler picks it up.
            new_intent = extracted.get("intent")
            if (
                new_intent in ("reschedule_appointment", "cancel_appointment", "view_appointments")
                and current_step in _BOOKING_RECOVERY_STEPS
                and not state.memory.get("selected_appointment_id")
                and not extracted.get("appointment_period")
                and not extracted.get("selected_appointment_index")
            ):
                extracted["intent"] = "booking"
                if extracted.get("new_date") and not extracted.get("date"):
                    extracted["date"] = extracted.pop("new_date")
                if extracted.get("new_time") and not extracted.get("time"):
                    extracted["time"] = extracted.pop("new_time")
                trace("INTENT", state.session_id,
                      f"contextual override: {new_intent!r} → booking "
                      f"(step={current_step!r}, booking recovery, no selected_appointment_id)")

            # Preconsultation guard: while the patient is answering symptom questions
            # (step is one of the collecting_* steps) any free-text reply is part of
            # the questionnaire, not a new intent. Force intent=preconsultation so
            # WorkflowNode's ACTIVE_STEPS guard keeps the step untouched.
            #
            # Hard pivots (geo_search, view_appointments, cancel_appointment,
            # reschedule_appointment, check_availability) are always allowed through
            # — the user is explicitly changing topic.
            #
            # Booking/doctor_search pivots are allowed ONLY when the LLM extracted
            # an explicit booking signal (doctor_name or specialty) that the user
            # actually typed.  Without this requirement, duration answers like
            # "1 day", "since yesterday", or "2 weeks" are misclassified as
            # intent=booking when a stale doctor_id is in memory context — the LLM
            # echoes the doctor_id into its JSON even though the user said nothing
            # about booking.
            new_intent = extracted.get("intent")
            if current_step in _PRECONSULTATION_ACTIVE_STEPS:
                _hard_pivot = new_intent in (
                    "geo_search",
                    "view_appointments",
                    "cancel_appointment",
                    "reschedule_appointment",
                    "check_availability",
                )
                _explicit_booking = (
                    new_intent in ("booking", "doctor_search")
                    and any(k in extracted for k in ("doctor_name", "specialty"))
                )
                if not _hard_pivot and not _explicit_booking:
                    extracted["intent"] = "preconsultation"
                    trace("INTENT", state.session_id,
                          f"preconsultation guard: forced intent=preconsultation "
                          f"(step={current_step!r}, LLM returned {new_intent!r}, "
                          f"no explicit booking signal in extracted)")

            # Preconsultation-complete booking guard: after the questionnaire the
            # patient sees a specialist recommendation and is asked "Would you like
            # me to find available Xs near you?".  A plain affirmative ("yes", "oui",
            # "نعم", …) is classified as intent=none by the LLM, which is then
            # preserved as intent=preconsultation by the ACTIVE_WORKFLOW_INTENTS guard
            # above — causing WorkflowNode to loop back into the summary.
            #
            # Fix: detect the affirmative and force intent=booking so WorkflowNode's
            # existing _reset_preconsult cross-workflow reset fires:
            #   • clear_preconsultation_state() wipes symptom_* fields
            #   • "specialty" key (set by _complete()) is NOT in PRECONSULTATION_FIELDS
            #     so it survives the reset
            #   • WorkflowNode routes to step=searching_doctors (specialty is set)
            #   • ActionNode → BookingHandler._searching_doctors() executes the search
            new_intent = extracted.get("intent")
            if current_step in {
                "preconsultation_complete",
                "awaiting_specialty_confirmation",
            } and new_intent not in {
                "booking", "doctor_search", "cancel_appointment",
                "view_appointments", "geo_search", "reschedule_appointment",
                "check_availability",
            }:
                words = set(re.split(r"\s+", state.message.lower().strip()))
                if words & _POSTCONSULT_AFFIRMATIVES:
                    extracted["intent"] = "booking"
                    trace("INTENT", state.session_id,
                          f"postconsult guard: forced intent=booking "
                          f"(affirmative at step={current_step!r}, words={words & _POSTCONSULT_AFFIRMATIVES})")

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

            # Language-preservation guard.
            # Two cases must not overwrite the established session language:
            #   1. Language-neutral messages ("1", "11:00", "2026-06-20"):
            #      the LLM reliably returns language="english" for these
            #      regardless of the actual session language.
            #   2. Active preconsultation steps: same problem for short
            #      symptom replies that look English to the LLM.
            _prev_lang     = state.memory.get("language")
            _detected_lang = extracted.get("language")
            _neutral       = _is_language_neutral(state.message)
            if (
                _prev_lang
                and _detected_lang
                and (_neutral or current_step in _PRECONSULTATION_ACTIVE_STEPS)
            ):
                extracted["language"] = _prev_lang

            trace("INTENT", state.session_id,
                  f"[LANG] previous={_prev_lang!r} "
                  f"detected={_detected_lang!r} "
                  f"final={extracted.get('language')!r} "
                  f"language_neutral={_neutral}")

            state.memory.update(extracted)

            # Record which keys were extracted this turn so ActionNode can
            # distinguish "fresh from current message" vs "loaded from Redis cache".
            # This is consumed by clear_stale_scheduling and never persisted.
            state.extracted_this_turn = set(extracted.keys())
            trace(
                "DEBUG_AFTER_INTENT",
                state.session_id,
                f"query={state.memory.get('query')!r} "
                f"specialty={state.memory.get('specialty')!r} "
                f"step={state.memory.get('step')!r} "
                f"doctor_name={state.memory.get('doctor_name')!r}"
            )
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

            # Fallback doctor_id extraction: the Find Doctors page sends
            # "Book an appointment with <name>, doctor ID: <id>". If the LLM
            # call itself failed (rate limit, network error, ...), this
            # explicit signal would otherwise be silently dropped — leaving a
            # stale step/intent in memory (e.g. selecting_doctor/doctor_search)
            # and stranding the user back in the previous search.
            _id_match = re.search(r"doctor\s*id[:\s]+([A-Za-z0-9_-]+)", state.message, re.IGNORECASE)
            if _id_match:
                state.memory["doctor_id"] = _id_match.group(1)
                state.memory["intent"] = "booking"
                state.extracted_this_turn = {"doctor_id", "intent"}

                _name_match = re.search(r"with\s+(.+?),\s*doctor\s*id", state.message, re.IGNORECASE)
                if _name_match:
                    state.memory["doctor_name"] = _name_match.group(1).strip()
                    state.extracted_this_turn.add("doctor_name")

                trace("INTENT", state.session_id,
                      f"fallback doctor_id extraction (LLM failed): "
                      f"doctor_id={_id_match.group(1)!r} "
                      f"doctor_name={state.memory.get('doctor_name')!r}, "
                      f"forced intent=booking")

        # ── Selecting-place guard (post-LLM, always runs) ─────────────────────
        # Must run OUTSIDE the try/except so it fires even on LLM failure
        # (429 rate-limit, parse error, etc.).
        #
        # Problem: when step=selecting_place and the LLM fails or returns
        # intent=none, the active-workflow guard preserves intent=geo_search.
        # WorkflowNode then sees geo_search+selecting_place → _reset_geo fires
        # → place_results cleared → search re-runs → list re-displayed.
        #
        # Fix: for a bare number message at selecting_place, unconditionally
        # set intent=select_doctor so WorkflowNode never triggers _reset_geo.
        if state.memory.get("step") == "selecting_place":
            try:
                _idx = int(state.message.strip())
                if 1 <= _idx <= 9:
                    prev_intent = state.memory.get("intent")
                    state.memory["intent"] = "select_doctor"
                    state.memory["selected_doctor_index"] = _idx
                    if not hasattr(state, "extracted_this_turn") or state.extracted_this_turn is None:
                        state.extracted_this_turn = set()
                    state.extracted_this_turn.update({"intent", "selected_doctor_index"})
                    trace("INTENT", state.session_id,
                          f"selecting_place post-guard: forced select_doctor "
                          f"idx={_idx} (was intent={prev_intent!r})")
            except (ValueError, AttributeError):
                pass

        # ── Selecting-doctor guard (post-LLM, always runs) ────────────────────
        # Problem: when step=selecting_doctor (doctor_results was just shown)
        # and the user replies with a number, a doctor's name, or taps a
        # doctor-card label (which embeds the doctor's name and a recommended
        # slot date/time), the LLM can classify the reply as
        # select_appointment / selected_appointment_index. WorkflowNode then
        # routes to selecting_appointment and the patient sees their EXISTING
        # appointments instead of continuing the booking with the chosen doctor.
        #
        # Fix: resolve the reply against doctor_results — prefer the LLM's own
        # positional index (mislabeled as selected_appointment_index), else a
        # bare number, else a name match — and force intent=select_doctor /
        # selected_doctor_index, overriding the select_appointment misclassification.
        if state.memory.get("step") == "selecting_doctor" and state.memory.get("intent") == "select_appointment":
            _doctors = state.memory.get("doctor_results") or []
            _resolved_idx = None

            _appt_idx = state.memory.get("selected_appointment_index")
            if isinstance(_appt_idx, int) and 1 <= _appt_idx <= len(_doctors):
                _resolved_idx = _appt_idx
            else:
                _msg = state.message.strip()
                try:
                    _n = int(_msg)
                    if 1 <= _n <= len(_doctors):
                        _resolved_idx = _n
                except ValueError:
                    _msg_lower = _msg.lower()
                    for _i, _doc in enumerate(_doctors, start=1):
                        _name = (_doc.get("name") or "").strip().lower()
                        if _name and (_name in _msg_lower or _msg_lower in _name):
                            _resolved_idx = _i
                            break

            if _resolved_idx is not None:
                prev_intent = state.memory.get("intent")
                state.memory["intent"] = "select_doctor"
                state.memory["selected_doctor_index"] = _resolved_idx
                state.memory.pop("selected_appointment_index", None)
                if not hasattr(state, "extracted_this_turn") or state.extracted_this_turn is None:
                    state.extracted_this_turn = set()
                state.extracted_this_turn.update({"intent", "selected_doctor_index"})
                state.extracted_this_turn.discard("selected_appointment_index")
                trace("INTENT", state.session_id,
                      f"selecting_doctor post-guard: forced select_doctor idx={_resolved_idx} "
                      f"(was intent={prev_intent!r}, doctors={len(_doctors)})")

        # ── Cross-session workflow resume guard (MED-3, post-LLM, always runs) ──
        # MemoryNode staged a snapshot of an abandoned workflow in
        # state.pending_workflow without merging it into state.memory.
        # Merge it now ONLY if this turn's intent is empty/"none" (vague
        # reply, likely "yes" to the resume hint) or matches the pending
        # workflow's own type — a brand-new, unrelated request never
        # silently inherits a stale step/doctor/date.
        _fresh_dbg = getattr(state, "extracted_this_turn", set()) or set()
        print(
            "[DEBUG_RESUME_GUARD]",
            "pending_workflow_present=", bool(state.pending_workflow),
            "memory_step=", repr(state.memory.get("step")),
            "memory_intent=", repr(state.memory.get("intent")),
            "workflow_type=", repr(state.pending_workflow.get("workflow_type") if state.pending_workflow else None),
            "memory_query=", repr(state.memory.get("query")),
            "memory_specialty=", repr(state.memory.get("specialty")),
            "doctor_name_present=", "doctor_name" in _fresh_dbg,
            "doctor_id_present=", "doctor_id" in _fresh_dbg,
            "extracted_this_turn=", sorted(_fresh_dbg),
        )
        if (
            state.pending_workflow
            and not state.memory.get("step")
            and (
                state.memory.get("intent") in (None, "none")
                or state.memory.get("intent") == state.pending_workflow.get("workflow_type")
            )
        ):
            snap = state.pending_workflow.get("state") or {}
            if not hasattr(state, "extracted_this_turn") or state.extracted_this_turn is None:
                state.extracted_this_turn = set()

            # If the user named a specific doctor THIS turn, that's a
            # brand-new, concrete request — don't resurrect the abandoned
            # snapshot's search context (query/specialty/doctor_results),
            # which would otherwise win over the fresh doctor_name in
            # _searching_doctors' "query or doctor_name or specialty"
            # resolution (e.g. a stale query="cardiologist" overriding a
            # fresh doctor_name="MHIRI Kais").
            _has_new_doctor = bool({"doctor_name", "doctor_id"} & state.extracted_this_turn)

            if snap and not _has_new_doctor:
                if snap.get("step") not in _PRECONSULTATION_ACTIVE_STEPS:
                    snap = {
                        k: v for k, v in snap.items()
                        if k not in _STALE_PRECONSULT_FIELDS
                    }

                # A specialty extracted (and normalized) THIS turn is a fresh,
                # concrete signal — don't let the snapshot's stale specialty
                # value overwrite it.
                _fresh_specialty = (
                    state.memory.get("specialty")
                    if "specialty" in state.extracted_this_turn
                    else None
                )

                state.memory.update(snap)

                if _fresh_specialty is not None:
                    state.memory["specialty"] = _fresh_specialty

                state.memory["workflow_started_at"] = time.time()
                state.extracted_this_turn.update(snap.keys())
                trace("INTENT", state.session_id,
                      f"cross-session resume: merged pending workflow "
                      f"| step={snap.get('step')!r} intent={snap.get('intent')!r}")
            elif snap:
                trace("INTENT", state.session_id,
                      f"cross-session resume SKIPPED — fresh doctor_name/doctor_id this turn "
                      f"| snap_step={snap.get('step')!r} snap_query={snap.get('query')!r} "
                      f"snap_specialty={snap.get('specialty')!r}")

        return state
