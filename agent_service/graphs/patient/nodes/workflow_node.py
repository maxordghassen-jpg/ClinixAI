import time

from app.memory.redis_memory import RedisMemory
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.workflow_state_cleaner import WorkflowStateCleaner


# Steps where ActionNode drives the logic directly.
# WorkflowNode must not re-route these based on intent.
ACTIVE_STEPS = {
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "ready_to_book",
    "searching_doctors",
    "searching_places",
    "awaiting_specialty",
    # Appointment management steps
    "fetching_appointments",
    "selecting_appointment",
    "confirming_cancel",
    "confirming_reschedule",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "awaiting_reschedule_slot_selection",
    "ready_to_reschedule",
    "saving_reminder_preference",
    "selecting_place",           # waiting for user to pick from a geo search result list
    "awaiting_slot_selection",   # after 409: waiting for user to pick an alternative slot
    "awaiting_recovery_choice",  # after 409 + no slots: user chooses from recovery menu
    # "selecting_doctor" is intentionally EXCLUDED:
    # when the user replies here with "1"/"2"/etc, IntentNode
    # returns intent="select_doctor" and WorkflowNode must be
    # allowed to process that and transition to "doctor_selected".
}

# Steps that belong to the booking flow (doctor search → date/time → book).
# Used by the cross-workflow reset logic below.
BOOKING_FLOW_STEPS: frozenset[str] = frozenset({
    "awaiting_specialty",
    "searching_doctors",
    "selecting_doctor",
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",  # post-409 slot recovery
    "awaiting_recovery_choice", # post-409 no-slots guided recovery menu
    "ready_to_book",
})

# Steps that belong to the appointment management flow (view/cancel/reschedule).
APPOINTMENT_FLOW_STEPS: frozenset[str] = frozenset({
    "fetching_appointments",
    "selecting_appointment",
    "confirming_cancel",
    "confirming_reschedule",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "awaiting_reschedule_slot_selection",
    "ready_to_reschedule",
})

# Steps that are exclusively part of the cancel sub-flow.
# Used to detect a reschedule intent arriving while cancel is active.
CANCEL_FLOW_STEPS: frozenset[str] = frozenset({
    "confirming_cancel",
})

# Steps that are exclusively part of the reschedule sub-flow.
# Used to detect a cancel intent arriving while reschedule is active.
RESCHEDULE_FLOW_STEPS: frozenset[str] = frozenset({
    "confirming_reschedule",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "awaiting_reschedule_slot_selection",
    "ready_to_reschedule",
})

# Intents that unambiguously start a new workflow incompatible with
# an active booking flow (doctor+date+time collection).
_BOOKING_INCOMPATIBLE = frozenset({
    "doctor_search",
    "geo_search",
    "view_appointments",
    "cancel_appointment",
    "reschedule_appointment",
})

# Intents incompatible with an active appointment management flow.
_APPT_INCOMPATIBLE = frozenset({
    "doctor_search",
    "booking",
    "geo_search",
})


class WorkflowNode:
    """
    Step-transition router.

    Reads intent + current context from state.memory and sets the correct
    workflow step. StateWriterNode persists everything at the end of the turn.

    Redis is used here ONLY for explicit key deletion during cross-workflow
    resets — a complementary operation to StateWriterNode's additive writes,
    not a replacement.
    """

    def __init__(self) -> None:
        self._redis = RedisMemory()

    async def run(self, state: AgentState) -> AgentState:

        memory = state.memory
        session_id = state.session_id
        current_step = memory.get("step")
        intent = memory.get("intent")

        # =====================================================
        # CROSS-WORKFLOW RESET
        #
        # Detect when the user starts a new, incompatible workflow
        # while an existing workflow is still in an active step.
        #
        # Without this check the ACTIVE_STEPS guard below would fire
        # and silently ignore the new intent, continuing the old step.
        # Example: user says "I want a dentist" while step=awaiting_time
        # → guard fires → ActionNode asks "What time?" — wrong.
        #
        # Three reset scenarios:
        #   A. New doctor search / cross-workflow during a booking flow
        #      "I want a dentist" | "Show my appointments" | "Find a pharmacy"
        #      while step ∈ BOOKING_FLOW_STEPS
        #   B. Booking / geo search during appointment management
        #      "Book an appointment" | "Find a clinic"
        #      while step ∈ APPOINTMENT_FLOW_STEPS
        #
        # On reset:
        #   - WorkflowStateCleaner wipes the stale field group from
        #     state.memory (dict)
        #   - delete_keys syncs the deletion to Redis immediately so
        #     the keys don't resurface on the next MemoryNode load
        #   - current_step is set to None → ACTIVE_STEPS guard skipped
        #   - normal intent routing continues below
        #
        # What is preserved:
        #   patient_id, language, specialty (just set by IntentNode),
        #   intent (just set), profile (read-only MongoDB)
        # =====================================================

        _reset_booking = (
            current_step in BOOKING_FLOW_STEPS
            and intent in _BOOKING_INCOMPATIBLE
        )
        _reset_appt = (
            current_step in APPOINTMENT_FLOW_STEPS
            and intent in _APPT_INCOMPATIBLE
        )

        if _reset_booking or _reset_appt:
            trace("WORKFLOW", session_id,
                  f"cross-workflow reset | step={current_step!r} → intent={intent!r} | "
                  f"scenario={'booking→new' if _reset_booking else 'appt→new'}")

            cleared: list[str] = []

            if _reset_booking:
                cleared += WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
            if _reset_appt:
                cleared += WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
                # Also wipe any booking remnants in case both flows overlapped
                cleared += WorkflowStateCleaner.clear_full_booking_state(memory, session_id)

            # Clear the active step so routing proceeds cleanly
            if memory.pop("step", None) is not None:
                cleared.append("step")

            current_step = None  # skip ACTIVE_STEPS guard below

            if cleared:
                await self._redis.delete_keys(session_id, cleared)
                trace("WORKFLOW", session_id,
                      f"reset complete — deleted from Redis: {cleared} | "
                      f"remaining keys: {sorted(memory.keys())}")

        # =====================================================
        # INTRA-APPOINTMENT CROSS-FLOW RESET
        #
        # Cancel and reschedule are both "appointment management"
        # but their steps are mutually exclusive.  When the user
        # switches intent while one of them is active (e.g. they
        # were in confirming_cancel and now want to reschedule,
        # or vice-versa) the ACTIVE_STEPS guard below would
        # silently continue the OLD flow — wrong.
        #
        # Detect this and reset the stale appointment state so
        # the new intent can route cleanly.
        # =====================================================

        _reset_cancel_to_reschedule = (
            current_step in CANCEL_FLOW_STEPS
            and intent == "reschedule_appointment"
        )
        _reset_reschedule_to_cancel = (
            current_step in RESCHEDULE_FLOW_STEPS
            and intent == "cancel_appointment"
        )

        if _reset_cancel_to_reschedule or _reset_reschedule_to_cancel:
            scenario = (
                "cancel→reschedule"
                if _reset_cancel_to_reschedule
                else "reschedule→cancel"
            )
            trace("WORKFLOW", session_id,
                  f"intra-appointment reset | step={current_step!r} → intent={intent!r} | "
                  f"scenario={scenario}")

            cleared = WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
            if memory.pop("step", None) is not None:
                cleared.append("step")
            current_step = None

            if cleared:
                await self._redis.delete_keys(session_id, cleared)
                trace("WORKFLOW", session_id,
                      f"intra-appointment reset complete — deleted from Redis: {cleared}")

        # =====================================================
        # ACTIVE WORKFLOW GUARD
        # If the session is already mid-flight, leave the step
        # untouched. ActionNode handles these steps directly.
        # =====================================================

        if current_step in ACTIVE_STEPS:
            trace("WORKFLOW", session_id,
                  f"active step guard — step unchanged: {current_step!r}")
            return state

        specialty = memory.get("specialty")
        doctor_id = memory.get("doctor_id")
        date = memory.get("date")
        time_value = memory.get("time")

        # =====================================================
        # WORKFLOW TIMER INITIALISATION
        # Set once when a new workflow starts. Never reset
        # mid-workflow so the 30-minute window is stable.
        # =====================================================

        if intent and intent != "none" and not memory.get("workflow_started_at"):
            memory["workflow_started_at"] = time.time()
            trace("WORKFLOW", session_id, f"timer initialised | intent={intent!r}")

        # =====================================================
        # DOCTOR SEARCH
        # =====================================================

        if intent == "doctor_search":
            if doctor_id:
                new_step = "awaiting_date" if not date else ("awaiting_time" if not time_value else "ready_to_book")
            else:
                new_step = "searching_doctors"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {new_step!r} | intent=doctor_search")
            memory["step"] = new_step

        # =====================================================
        # SELECT DOCTOR
        # =====================================================

        elif intent == "select_doctor":
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'doctor_selected' | intent=select_doctor")
            memory["step"] = "doctor_selected"

        # =====================================================
        # BOOKING FLOW
        # =====================================================

        elif intent == "booking":
            if not doctor_id:
                new_step = "searching_doctors" if specialty else "awaiting_specialty"
            elif not date:
                new_step = "awaiting_date"
            elif not time_value:
                new_step = "awaiting_time"
            else:
                new_step = "ready_to_book"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {new_step!r} | intent=booking "
                  f"| doctor_id={bool(doctor_id)} date={bool(date)} time={bool(time_value)}")
            memory["step"] = new_step

        # =====================================================
        # VIEW APPOINTMENTS
        # =====================================================

        elif intent == "view_appointments":
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'fetching_appointments' | intent=view_appointments")
            memory["step"] = "fetching_appointments"

        # =====================================================
        # CANCEL APPOINTMENT
        # =====================================================

        elif intent == "cancel_appointment":
            # If an appointment is already identified in memory, go straight to confirm.
            # Otherwise fetch the list first so the patient can select one.
            if memory.get("selected_appointment_id"):
                new_step = "confirming_cancel"
            else:
                new_step = "fetching_appointments"
            memory["pending_action"] = "cancel"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {new_step!r} | intent=cancel_appointment")
            memory["step"] = new_step

        # =====================================================
        # RESCHEDULE APPOINTMENT
        # =====================================================

        elif intent == "reschedule_appointment":
            # Always enter through confirming_reschedule when an appointment is
            # already identified, so the user sees what they are rescheduling
            # before date/time collection begins.
            if memory.get("selected_appointment_id"):
                new_step = "confirming_reschedule"
            else:
                new_step = "fetching_appointments"
            memory["pending_action"] = "reschedule"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {new_step!r} | intent=reschedule_appointment")
            memory["step"] = new_step

        # =====================================================
        # SELECT APPOINTMENT (from a displayed list)
        # =====================================================

        elif intent == "select_appointment":
            # Always route through selecting_appointment so ActionNode can:
            #   1. resolve selected_appointment_index against appointment_list
            #   2. hydrate selected_appointment_id / doctor / date / time
            #   3. then route to confirming_cancel or confirming_reschedule
            #
            # Never jump directly to a confirm step: appt_id would be None.
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'selecting_appointment' | intent=select_appointment")
            memory["step"] = "selecting_appointment"

        # =====================================================
        # SET REMINDER PREFERENCE
        # =====================================================

        elif intent == "set_reminder":
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'saving_reminder_preference' | intent=set_reminder")
            memory["step"] = "saving_reminder_preference"

        # =====================================================
        # GEO SEARCH
        # =====================================================

        elif intent == "geo_search":
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'searching_places' | intent=geo_search")
            memory["step"] = "searching_places"

        # =====================================================
        # CANCEL (legacy — kept for backward compat, maps to same flow)
        # =====================================================

        elif intent == "cancel":
            memory["pending_action"] = "cancel"
            if memory.get("selected_appointment_id"):
                memory["step"] = "confirming_cancel"
            else:
                memory["step"] = "fetching_appointments"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {memory['step']!r} | intent=cancel (legacy)")

        # =====================================================
        # NO INTENT — keep previous step if present
        # =====================================================

        else:
            if not memory.get("step"):
                memory["step"] = "idle"
                trace("WORKFLOW", session_id,
                      f"no intent — step set to idle | intent={intent!r}")
            else:
                trace("WORKFLOW", session_id,
                      f"no intent — step unchanged: {current_step!r}")

        return state
