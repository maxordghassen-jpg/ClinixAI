"""
Workflow-scoped transient state cleaner.

Responsibility: identify and remove field groups from state.memory (the
in-memory dict) when a workflow phase boundary is crossed.

Design rules:
- Pure dict manipulation — no Redis calls, no I/O.
- Returns the list of actually-cleared keys so the caller can:
    a) pass them to RedisMemory.delete_keys() for immediate sync, AND
    b) include them in trace logs for observability.
- StateWriterNode handles additive writes (ContextMerger never deletes).
  Stale key removal requires an explicit delete_keys call — this helper
  identifies what to delete; the calling node executes it. That keeps a
  single, auditable deletion path per call site.

Field group rationale
---------------------
BOOKING_SCHEDULING_FIELDS
    Collected during one booking attempt: date, time, and their cached
    normalised forms. Stale values from a previous session can silently
    skip the date/time collection steps and trigger an immediate booking
    against a different doctor — causing 409 conflicts and misleading
    "no slots" messages.  Must be cleared whenever a new doctor is
    selected so the user is always asked for fresh date/time.

    Preserved by exclusion: patient_id, language, specialty,
    doctor_results, doctor_id/name (just written by the caller),
    intent, step, workflow_started_at, profile.

FULL_BOOKING_STATE_FIELDS
    Everything belonging to an in-progress booking: the chosen doctor
    context AND the scheduling fields.  Required when a cross-workflow
    reset occurs (e.g., user asks for a new doctor while awaiting_time)
    so that no stale doctor_id / date / time survives into the new flow.

    Preserved by exclusion: patient_id, language, specialty (just
    updated by IntentNode), intent (just updated), workflow_started_at.

APPOINTMENT_SELECTION_FIELDS
    Set during cancel/reschedule list navigation: the selected
    appointment, the displayed list, and the pending action.  A stale
    selected_appointment_id would auto-advance the cancel/reschedule
    workflow past list presentation on re-entry.  Clear when starting a
    fresh cancel or reschedule flow.

    Preserved by exclusion: patient_id, language, appointment_period
    preference, intent, step.

RESCHEDULE_FIELDS
    The new date/time being collected for a reschedule in progress.
    A stale new_date / new_time would skip user input and attempt a
    reschedule with wrong values.  Clear when retrying a reschedule
    (e.g. after a normalisation error) while keeping appointment context.

    Preserved by exclusion: selected_appointment_id and all fields set
    by the appointment selection step.
"""

from __future__ import annotations

from graphs.shared.trace import trace


# ── Field groups ──────────────────────────────────────────────────────────────

# Scheduling state for a single booking attempt.
BOOKING_SCHEDULING_FIELDS: frozenset[str] = frozenset({
    "date",               # appointment date as provided by the user
    "time",               # appointment time as provided by the user
    "normalized_date",    # ISO-normalised date (cached by normalizer)
    "normalized_time",    # HH:MM-normalised time (cached by normalizer)
    "suggested_slots",    # free-slot list previously shown to the user
    "availability_cache", # raw availability payload (request-level cache)
    "booking_candidate",  # draft booking object (forward-compat placeholder)
})

# State set during cancel / reschedule appointment list navigation.
APPOINTMENT_SELECTION_FIELDS: frozenset[str] = frozenset({
    "selected_appointment_id",
    "selected_appointment_doctor",
    "selected_appointment_doctor_id",
    "selected_appointment_date",
    "selected_appointment_time",
    "selected_appointment_index",
    "appointment_list",
    "pending_action",
})

# All booking flow state — doctor context + scheduling.
# Used for cross-workflow resets where the entire booking context must be wiped.
FULL_BOOKING_STATE_FIELDS: frozenset[str] = frozenset({
    # Doctor context set during doctor_selected / searching_doctors
    "doctor_id",
    "doctor_name",
    "doctor_results",
    "selected_doctor_index",
    # Scheduling state (superset of BOOKING_SCHEDULING_FIELDS)
    "date",
    "time",
    "normalized_date",
    "normalized_time",
    "suggested_slots",
    "availability_cache",
    "booking_candidate",
    # Recovery state (set when booking fails with no available slots)
    "recovery_context",
})

# New date/time being collected during an active reschedule.
RESCHEDULE_FIELDS: frozenset[str] = frozenset({
    "new_date",
    "new_time",
})

# Everything set during appointment management (cancel + reschedule).
ALL_APPOINTMENT_FIELDS: frozenset[str] = (
    APPOINTMENT_SELECTION_FIELDS | RESCHEDULE_FIELDS
)


# ── Helper ────────────────────────────────────────────────────────────────────

class WorkflowStateCleaner:
    """
    Pure in-memory helper for clearing workflow-scoped transient state.

    Usage pattern in any ActionNode handler:

        cleaner = WorkflowStateCleaner()
        cleared = cleaner.clear_booking_scheduling(memory, session_id)
        if cleared:
            await self.memory.delete_keys(session_id, cleared)
    """

    # ── Public API ────────────────────────────────────────────────────────────

    @staticmethod
    def clear_stale_scheduling(
        memory: dict,
        fresh_fields: set[str],
        session_id: str = "",
    ) -> list[str]:
        """
        Clear only the BOOKING_SCHEDULING_FIELDS not present in fresh_fields.

        fresh_fields is state.extracted_this_turn — the keys the LLM just
        extracted from the current message.  Fields the user just provided
        are never stale; everything else in BOOKING_SCHEDULING_FIELDS may
        be a leftover from a previous session or workflow attempt.

        Example — user says "I want a dentist tomorrow at 9":
          fresh_fields = {"intent","specialty","date","time","language"}
          → preserves: date, time  (just extracted)
          → clears:    normalized_date, normalized_time, suggested_slots, …

        Example — user says "I need a dentist" (stale date in Redis):
          fresh_fields = {"intent","specialty","language"}
          → clears: date, time, normalized_date, normalized_time, …

        Call this at the START of searching_doctors / searching_places to
        purge stale scheduling state the user did not re-supply this turn.
        Returns the list of cleared keys for Redis deletion and logging.
        """
        stale = BOOKING_SCHEDULING_FIELDS - fresh_fields
        return WorkflowStateCleaner._clear_fields(
            memory,
            frozenset(stale),
            session_id,
            context=(
                f"stale_scheduling | "
                f"fresh={sorted(fresh_fields & BOOKING_SCHEDULING_FIELDS) or 'none'}"
            ),
        )

    @staticmethod
    def clear_booking_scheduling(
        memory: dict,
        session_id: str = "",
    ) -> list[str]:
        """
        Clear booking scheduling fields before a new doctor-selected flow.

        Call this in doctor_selected before setting step=awaiting_date.
        Returns the list of cleared keys for Redis deletion and logging.
        """
        return WorkflowStateCleaner._clear_fields(
            memory,
            BOOKING_SCHEDULING_FIELDS,
            session_id,
            context="booking_scheduling",
        )

    @staticmethod
    def clear_appointment_selection(
        memory: dict,
        session_id: str = "",
    ) -> list[str]:
        """
        Clear appointment selection fields when starting a fresh
        cancel or reschedule flow from scratch.

        Returns the list of cleared keys for Redis deletion and logging.
        """
        return WorkflowStateCleaner._clear_fields(
            memory,
            APPOINTMENT_SELECTION_FIELDS,
            session_id,
            context="appointment_selection",
        )

    @staticmethod
    def clear_reschedule_dates(
        memory: dict,
        session_id: str = "",
    ) -> list[str]:
        """
        Clear new_date / new_time when retrying a reschedule after an error.

        Preserves selected_appointment_id and all appointment context.
        Returns the list of cleared keys for Redis deletion and logging.
        """
        return WorkflowStateCleaner._clear_fields(
            memory,
            RESCHEDULE_FIELDS,
            session_id,
            context="reschedule_dates",
        )

    @staticmethod
    def clear_full_booking_state(
        memory: dict,
        session_id: str = "",
    ) -> list[str]:
        """
        Clear all booking flow state for a cross-workflow reset.

        Used by WorkflowNode when a doctor_search or incompatible intent
        arrives while a booking workflow is active (e.g. step=awaiting_time).
        Clears doctor context AND scheduling fields so the new workflow
        starts with a completely clean slate.

        Preserved by exclusion: patient_id, language, specialty (just
        written by IntentNode), intent (just written), workflow_started_at.
        Returns the list of cleared keys for Redis deletion and logging.
        """
        return WorkflowStateCleaner._clear_fields(
            memory,
            FULL_BOOKING_STATE_FIELDS,
            session_id,
            context="full_booking_state",
        )

    @staticmethod
    def clear_all_appointment_state(
        memory: dict,
        session_id: str = "",
    ) -> list[str]:
        """
        Clear all appointment management state for a cross-workflow reset.

        Used by WorkflowNode when a booking/geo intent arrives while an
        appointment management workflow is active (e.g. step=confirming_cancel).
        Returns the list of cleared keys for Redis deletion and logging.
        """
        return WorkflowStateCleaner._clear_fields(
            memory,
            ALL_APPOINTMENT_FIELDS,
            session_id,
            context="all_appointment_state",
        )

    # ── Internal ──────────────────────────────────────────────────────────────

    @staticmethod
    def _clear_fields(
        memory: dict,
        fields: frozenset[str],
        session_id: str,
        context: str,
    ) -> list[str]:
        """
        Remove every key in `fields` that is present in `memory`.

        Logs the before-values and the cleared key list for post-mortem
        debugging of stale-state incidents.  Returns the cleared keys.
        """
        before: dict = {k: memory[k] for k in fields if k in memory}
        cleared: list[str] = list(before.keys())

        for key in cleared:
            del memory[key]

        if cleared:
            trace(
                "STATE_CLEANER",
                session_id,
                f"[{context}] cleared {len(cleared)} field(s): {cleared} | "
                f"stale_values={before}",
            )
        else:
            trace(
                "STATE_CLEANER",
                session_id,
                f"[{context}] no stale fields present — memory already clean",
            )

        return cleared
