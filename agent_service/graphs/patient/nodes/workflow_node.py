import time

from app.memory.redis_memory import RedisMemory
from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.workflow_state_cleaner import WorkflowStateCleaner


# Steps that belong to the preconsultation questionnaire flow.
PRECONSULTATION_FLOW_STEPS: frozenset[str] = frozenset({
    "collecting_chief_complaint",
    "collecting_duration",
    "collecting_severity",
    "collecting_associated",
    "preconsultation_complete",
    "awaiting_specialty_confirmation",
})

# Booking-variant preconsultation steps (Scenario 2: doctor/date/time were
# already selected before the questionnaire runs). IntentNode forces
# intent="preconsultation" for every ordinary reply during these steps, but
# they are also members of BOOKING_FLOW_STEPS. That combination must not be
# treated as a hard pivot away from booking — see _reset_booking below.
PRECONSULTATION_BOOKING_STEPS: frozenset[str] = frozenset({
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
})

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
    "awaiting_availability_recovery",  # doctor has no availability schedule: guided recovery menu
    # Availability check steps
    "awaiting_availability_date",  # waiting for patient to name a date for availability check
    # Preconsultation steps — ActionNode (SymptomCollectionHandler) owns these
    "collecting_chief_complaint",
    "collecting_duration",
    "collecting_severity",
    "collecting_associated",
    "preconsultation_complete",
    "awaiting_specialty_confirmation",
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
    # "selecting_doctor" is intentionally EXCLUDED:
    # when the user replies here with "1"/"2"/etc, IntentNode
    # returns intent="select_doctor" and WorkflowNode must be
    # allowed to process that and transition to "doctor_selected".
    # "checking_availability_doctor" is intentionally EXCLUDED:
    # WorkflowNode sets it fresh each turn from check_availability intent.
}

# Steps that belong to the geo search flow (place search → selection).
# Used by the cross-workflow reset logic below.
GEO_FLOW_STEPS: frozenset[str] = frozenset({
    "searching_places",
    "selecting_place",
})

# Steps that belong to the booking flow (doctor search → date/time → book).
# Used by the cross-workflow reset logic below.
BOOKING_FLOW_STEPS: frozenset[str] = frozenset({
    "awaiting_specialty",
    "searching_doctors",
    "selecting_doctor",
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
    "awaiting_slot_selection",  # post-409 slot recovery
    "awaiting_recovery_choice", # post-409 no-slots guided recovery menu
    "awaiting_availability_recovery", # no availability schedule guided recovery menu
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
    "check_availability",   # availability check pivots away from booking
    "preconsultation",      # symptom report must reset stale booking state
})

# Intents incompatible with an active appointment management flow.
_APPT_INCOMPATIBLE = frozenset({
    "doctor_search",
    "booking",
    "geo_search",
    "check_availability",
    "preconsultation",      # symptom report interrupts appointment management
})

# Steps that belong to the availability check flow.
AVAIL_CHECK_FLOW_STEPS: frozenset[str] = frozenset({
    "awaiting_availability_date",
    # checking_availability_doctor is transient — not included (re-set each turn)
})

# Intents that interrupt an active availability check flow.
_AVAIL_CHECK_INCOMPATIBLE = frozenset({
    "booking",
    "doctor_search",
    "geo_search",
    "view_appointments",
    "cancel_appointment",
    "reschedule_appointment",
    "preconsultation",      # symptom report interrupts availability check
})

# Intents that interrupt an active preconsultation questionnaire.
# Hard pivots (booking a different flow) reset the questionnaire.
_PRECONSULTATION_INCOMPATIBLE = frozenset({
    "booking",
    "doctor_search",
    "geo_search",
    "view_appointments",
    "cancel_appointment",
    "reschedule_appointment",
    "check_availability",
})

# Intents that must interrupt an active geo search flow.
# Covers: user pivots from viewing place results to booking/management.
# Also includes geo_search itself so that a new place query replaces old results.
_GEO_INCOMPATIBLE = frozenset({
    "booking",
    "doctor_search",
    "view_appointments",
    "cancel_appointment",
    "reschedule_appointment",
    "geo_search",           # new search replaces stale selecting_place results
    "preconsultation",      # symptom report interrupts place browsing
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
            and not (
                intent == "preconsultation"
                and current_step in PRECONSULTATION_BOOKING_STEPS
            )
        )
        _reset_appt = (
            current_step in APPOINTMENT_FLOW_STEPS
            and intent in _APPT_INCOMPATIBLE
        )
        _reset_geo = (
            current_step in GEO_FLOW_STEPS
            and intent in _GEO_INCOMPATIBLE
        )
        _reset_avail = (
            current_step in AVAIL_CHECK_FLOW_STEPS
            and intent in _AVAIL_CHECK_INCOMPATIBLE
        )
        _reset_preconsult = (
            current_step in PRECONSULTATION_FLOW_STEPS
            and current_step != "awaiting_specialty_confirmation"
            and intent in _PRECONSULTATION_INCOMPATIBLE
        )

        if _reset_booking or _reset_appt or _reset_geo or _reset_avail or _reset_preconsult:
            if _reset_geo:
                scenario = "geo→new"
            elif _reset_booking:
                scenario = "booking→new"
            elif _reset_avail:
                scenario = "avail→new"
            elif _reset_preconsult:
                scenario = "preconsult→new"
            else:
                scenario = "appt→new"

            trace("WORKFLOW", session_id,
                  f"cross-workflow reset | step={current_step!r} → intent={intent!r} | "
                  f"scenario={scenario}")

            cleared: list[str] = []

            if _reset_geo:
                cleared += WorkflowStateCleaner.clear_geo_state(memory, session_id)
            if _reset_booking or _reset_avail:
                cleared += WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
            if _reset_appt:
                cleared += WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
                # Also wipe any booking remnants in case both flows overlapped
                cleared += WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
            if _reset_preconsult:
                cleared += WorkflowStateCleaner.clear_preconsultation_state(memory, session_id)
                # Wipe stale booking context so the new booking flow starts clean.
                # Without this, leftover doctor_id/date/time from a previous session
                # cause WorkflowNode to route straight to ready_to_book.
                cleared += WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
                if memory.pop("query", None) is not None:
                    cleared.append("query")

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
        # BOOKING DOCTOR-NAME OVERRIDE
        #
        # Scenario: workflow is paused at awaiting_specialty or
        # searching_doctors (early doctor-discovery steps) and the
        # user names a specific doctor in the current message.
        #
        # Why the guards above don't catch this:
        #   • cross-workflow reset: intent=booking is not in
        #     _BOOKING_INCOMPATIBLE (booking vs. booking is not a
        #     cross-workflow switch by that logic)
        #   • intra-appointment reset: unrelated flow
        #
        # Result without this fix: ACTIVE_STEPS guard fires below,
        # returns early, ActionNode re-asks "Quel médecin ?" — wrong.
        #
        # Fix: if doctor_name was freshly extracted this turn
        # (∈ extracted_this_turn), clear the stale step from memory
        # and Redis so normal routing proceeds.  The booking branch
        # then routes to searching_doctors (doctor_name is the query).
        # =====================================================

        fresh = getattr(state, "extracted_this_turn", set())
        _reset_for_doctor_name = (
            intent == "booking"
            and "doctor_name" in fresh
            and current_step in {"awaiting_specialty", "searching_doctors"}
        )

        if _reset_for_doctor_name:
            trace("WORKFLOW", session_id,
                  f"doctor-name override | step={current_step!r} cleared "
                  f"→ will route to searching_doctors | "
                  f"doctor_name={memory.get('doctor_name')!r}")
            if memory.pop("step", None) is not None:
                await self._redis.delete_keys(session_id, ["step"])
            current_step = None  # skip ACTIVE_STEPS guard below

        # =====================================================
        # STALE DOCTOR-ID GUARD
        # When a NEW doctor_name is extracted this turn and a
        # doctor_id from a PREVIOUS booking already lives in
        # Redis, the booking branch would skip searching_doctors
        # and proceed straight to awaiting_date with the wrong
        # doctor.  Clear the stale ID (and related search state)
        # so the booking branch always runs a fresh name search.
        #
        # Guard: doctor_id NOT in fresh_fields — if the caller
        # supplied an explicit ID in the same message (e.g.
        # "Book with Dr X, ID: doc-123") that ID is intentional
        # and must be preserved.
        # =====================================================

        if intent == "booking" and "doctor_name" in fresh:
            _stale_id = memory.get("doctor_id")
            if _stale_id and "doctor_id" not in fresh:
                trace("WORKFLOW", session_id,
                      f"stale doctor_id guard | "
                      f"prev_doctor_id={_stale_id!r} "
                      f"new_doctor_name={memory.get('doctor_name')!r} | "
                      f"clearing doctor_id, doctor_results, selected_doctor_index")
                for _k in ("doctor_id", "doctor_results", "selected_doctor_index"):
                    memory.pop(_k, None)
                await self._redis.delete_keys(
                    session_id,
                    ["doctor_id", "doctor_results", "selected_doctor_index"],
                )

        if current_step == "preconsultation_complete" and memory.get("preconsultation_done"):
            memory["step"] = "awaiting_specialty_confirmation"
            current_step = "awaiting_specialty_confirmation"
            trace("WORKFLOW", session_id,
                  "transition: preconsultation_complete -> awaiting_specialty_confirmation")

        if (
            current_step == "awaiting_specialty_confirmation"
            and intent == "booking"
            and memory.get("specialty")
        ):
            memory["step"] = "searching_doctors"
            current_step = "searching_doctors"
            trace("WORKFLOW", session_id,
                  "transition: awaiting_specialty_confirmation -> searching_doctors")

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
                new_step = (
                    "awaiting_date"
                    if not date
                    else (
                        "awaiting_time"
                        if not time_value
                        else (
                            "ready_to_book"
                            if memory.get("preconsultation_done")
                            else "collecting_chief_complaint_booking"
                        )
                    )
                )
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
            if doctor_id:
                # ID already resolved — skip search entirely
                if not date:
                    new_step = "awaiting_date"
                elif not time_value:
                    new_step = "awaiting_time"
                else:
                    new_step = (
                        "ready_to_book"
                        if memory.get("preconsultation_done")
                        else "collecting_chief_complaint_booking"
                    )
            elif memory.get("doctor_name"):
                # Doctor named but no ID yet — search by name; _searching_doctors
                # uses doctor_name as query, auto-selects on a unique match.
                new_step = "searching_doctors"
            elif specialty:
                new_step = "searching_doctors"
            else:
                new_step = "awaiting_specialty"
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → {new_step!r} | intent=booking "
                  f"| doctor_id={bool(doctor_id)} doctor_name={memory.get('doctor_name')!r} "
                  f"specialty={bool(specialty)} date={bool(date)} time={bool(time_value)}")
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
        # CHECK AVAILABILITY (specific doctor + date)
        # =====================================================

        elif intent == "check_availability":
            trace("WORKFLOW", session_id,
                  f"step: {current_step!r} → 'checking_availability_doctor' | "
                  f"intent=check_availability | "
                  f"doctor_name={memory.get('doctor_name')!r} date={memory.get('date')!r}")
            memory["step"] = "checking_availability_doctor"

        # =====================================================
        # PRECONSULTATION
        # Start the symptom questionnaire unless one is already
        # complete for this session (preconsultation_done=True).
        # =====================================================

        elif intent == "preconsultation":
            if memory.get("preconsultation_done"):
                # Already completed this session — just acknowledge
                trace("WORKFLOW", session_id,
                      f"preconsultation already done this session — idle")
                memory["step"] = "idle"
            elif doctor_id and date and time_value:
                # Booking already resolved (doctor + date + time set) before
                # this symptom report — use the "_booking" variant so
                # completing the questionnaire routes straight to
                # ready_to_book, preserving the selected doctor/date/time
                # instead of restarting via awaiting_specialty_confirmation
                # → searching_doctors.
                new_step = "collecting_chief_complaint_booking"
                trace("WORKFLOW", session_id,
                      f"step: {current_step!r} → {new_step!r} | intent=preconsultation "
                      f"(doctor_id/date/time already set — booking variant)")
                memory["step"] = new_step
            else:
                new_step = memory.get("step") or "collecting_chief_complaint"
                # If we're not already in the middle of collection, start fresh
                if new_step not in PRECONSULTATION_FLOW_STEPS:
                    new_step = "collecting_chief_complaint"
                trace("WORKFLOW", session_id,
                      f"step: {current_step!r} → {new_step!r} | intent=preconsultation")
                memory["step"] = new_step

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
