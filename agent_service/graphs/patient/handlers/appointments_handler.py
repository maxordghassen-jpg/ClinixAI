"""
Appointments workflow handler.

Covers appointment viewing, cancellation, and rescheduling flows.

Steps owned:
    fetching_appointments, selecting_appointment,
    confirming_reschedule, confirming_cancel,
    awaiting_reschedule_date, awaiting_reschedule_time,
    ready_to_reschedule, awaiting_reschedule_slot_selection,
    saving_reminder_preference, ready_to_cancel
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.booking_responses import BookingResponses
from graphs.shared.workflow_state_cleaner import WorkflowStateCleaner
from graphs.shared.slot_formatter import SlotFormatter
from graphs.shared.normalizers.date_normalizer import DateNormalizer
from graphs.shared.normalizers.time_normalizer import TimeNormalizer

from graphs.patient.handlers.helpers import (
    _NEGATIVE_WORDS,
    _is_availability_exploration,
    _format_status,
)

# Steps this handler owns — used by ActionNode to route.
STEPS: frozenset[str] = frozenset({
    "fetching_appointments",
    "selecting_appointment",
    "confirming_reschedule",
    "confirming_cancel",
    "awaiting_reschedule_date",
    "awaiting_reschedule_time",
    "ready_to_reschedule",
    "awaiting_reschedule_slot_selection",
    "saving_reminder_preference",
    "ready_to_cancel",
})


class AppointmentsHandler:
    """Handles all appointment view / cancel / reschedule workflow steps."""

    def __init__(
        self,
        *,
        tools: Any,
        redis_memory: Any,
        availability_service: Any,
        next_available: Any,
        name_hydrator: Any,
        patient_memory: Any,
        run_fn: Callable[[AgentState], Coroutine[Any, Any, AgentState]],
    ) -> None:
        self.tools = tools
        self.memory = redis_memory
        self.availability_service = availability_service
        self.next_available = next_available
        self.name_hydrator = name_hydrator
        self.patient_memory = patient_memory
        self._run = run_fn

    async def handle(self, state: AgentState) -> AgentState:
        step = state.memory.get("step")
        if step == "fetching_appointments":
            return await self._fetching_appointments(state)
        if step == "selecting_appointment":
            return await self._selecting_appointment(state)
        if step == "confirming_reschedule":
            return await self._confirming_reschedule(state)
        if step == "confirming_cancel":
            return await self._confirming_cancel(state)
        if step == "awaiting_reschedule_date":
            return await self._awaiting_reschedule_date(state)
        if step == "awaiting_reschedule_time":
            return await self._awaiting_reschedule_time(state)
        if step == "ready_to_reschedule":
            return await self._ready_to_reschedule(state)
        if step == "awaiting_reschedule_slot_selection":
            return await self._awaiting_reschedule_slot_selection(state)
        if step == "saving_reminder_preference":
            return await self._saving_reminder_preference(state)
        if step == "ready_to_cancel":
            return await self._ready_to_cancel(state)
        return state

    # =========================================================================
    # FETCH APPOINTMENTS (retrieval + cancel/reschedule setup)
    # =========================================================================

    async def _fetching_appointments(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        patient_id = state.patient_id or memory.get("patient_id")
        period = memory.get("appointment_period", "week")
        pending_action = memory.get("pending_action")

        trace("ACTION", session_id,
              f"fetching_appointments | patient={patient_id} period={period!r} "
              f"pending_action={pending_action!r}")

        try:
            if period == "today":
                appointments = await self.tools.get_patient_appointments_today(patient_id)
            elif period == "next_week":
                appointments = await self.tools.get_patient_appointments_next_week(patient_id)
            else:
                appointments = await self.tools.get_patient_appointments_week(patient_id)
        except Exception as exc:
            trace("ACTION", session_id, f"appointment fetch ERROR: {exc}")
            state.response = "Unable to retrieve your appointments right now. Please try again."
            return state

        if not appointments:
            state.response = BookingResponses.get(language, "no_appointments")
            memory["step"] = "idle"
            return state

        # Build appointment list with doctor_id preserved for hydration.
        raw_list = [
            {
                "appointment_id": a.get("id", ""),
                "doctor_id": a.get("doctor_id", ""),
                "doctor_name": a.get("doctor_name", ""),
                "date": str(a.get("date", ""))[:10],
                "time": a.get("time", ""),
                "status": a.get("status", ""),
            }
            for a in (appointments if isinstance(appointments, list) else [])
        ]
        trace("ACTION", session_id,
              f"raw appointment list ({len(raw_list)}): "
              f"{[{'id': a['appointment_id'], 'doctor_id': a['doctor_id']} for a in raw_list]}")

        # Batch-hydrate doctor names from geo_service /api/doctors/lookup.
        hydrated_list = await self.name_hydrator.hydrate(raw_list, session_id)
        memory["appointment_list"] = hydrated_list

        trace("ACTION", session_id,
              f"hydrated appointment list: "
              f"{[{'id': a['appointment_id'], 'doctor': a['doctor_name']} for a in hydrated_list]}")

        lines = [BookingResponses.get(language, "appointments_header")]
        for i, appt in enumerate(memory["appointment_list"], start=1):
            lines.append(BookingResponses.get(
                language, "appointment_line",
                index=i,
                doctor_name=appt["doctor_name"],
                date=appt["date"],
                time=appt["time"],
                status=_format_status(appt["status"], language),
            ))

        if pending_action in ("cancel", "reschedule"):
            memory["step"] = "selecting_appointment"

            # Fast-path: if the user already supplied their selection in the same
            # message ("cancel the first appointment"), resolve immediately instead
            # of showing the list and forcing them to repeat the index.
            if memory.get("selected_appointment_index") is not None:
                trace("ACTION", session_id,
                      f"selected_appointment_index={memory['selected_appointment_index']} "
                      f"already in memory — fast-pathing to selecting_appointment")
                state.response = "\n".join(lines)
                return await self._run(state)

            lines.append("\n" + BookingResponses.get(language, "select_appointment"))
        else:
            memory["step"] = "idle"

        state.response = "\n".join(lines)
        trace("ACTION", session_id,
              f"listed {len(memory['appointment_list'])} appointment(s) | "
              f"step={memory['step']!r}")
        return state

    # =========================================================================
    # SELECTING APPOINTMENT (from list, for cancel/reschedule)
    # =========================================================================

    async def _selecting_appointment(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        appointment_list = memory.get("appointment_list", [])
        selected_index = memory.get("selected_appointment_index")
        pending = memory.get("pending_action", "cancel")

        trace("ACTION", session_id,
              f"selecting_appointment | raw_index={selected_index!r} | "
              f"list_size={len(appointment_list)} | pending_action={pending!r}")

        if selected_index is None:
            trace("ACTION", session_id,
                  "selected_appointment_index missing — re-prompting user")
            state.response = BookingResponses.get(language, "select_appointment")
            return state

        position = int(selected_index) - 1

        if not appointment_list:
            trace("ACTION", session_id,
                  "appointment_list empty — cannot resolve index; re-fetching")
            memory["step"] = "fetching_appointments"
            return await self._run(state)

        if position < 0 or position >= len(appointment_list):
            trace("ACTION", session_id,
                  f"index out of range: {selected_index} (max {len(appointment_list)}) — "
                  f"asking user to re-select")
            state.response = BookingResponses.get(language, "appointment_not_found")
            return state

        selected = appointment_list[position]
        memory["selected_appointment_id"]          = selected["appointment_id"]
        memory["selected_appointment_doctor"]      = selected["doctor_name"]
        memory["selected_appointment_doctor_id"]   = selected["doctor_id"]
        memory["selected_appointment_date"]        = selected["date"]
        memory["selected_appointment_time"]        = selected["time"]
        # Consumed — clear so it doesn't bleed into the next turn
        memory.pop("selected_appointment_index", None)
        await self.memory.delete_keys(state.session_id, ["selected_appointment_index"])

        trace("ACTION", session_id,
              f"appointment resolved: index={selected_index} → "
              f"id={selected['appointment_id']!r} | "
              f"doctor={selected['doctor_name']!r} (id={selected['doctor_id']!r}) | "
              f"date={selected['date']!r} | time={selected['time']!r} | "
              f"pending_action={pending!r}")

        if pending == "reschedule":
            memory["step"] = "confirming_reschedule"
            state.response = BookingResponses.get(
                language, "reschedule_confirm_prompt",
                doctor_name=selected["doctor_name"],
                date=selected["date"],
                time=selected["time"],
            )
            trace("ACTION", session_id,
                  f"selection complete → confirming_reschedule | "
                  f"appt_id={selected['appointment_id']!r}")
        else:
            memory["step"] = "confirming_cancel"
            state.response = BookingResponses.get(
                language, "cancel_confirm_prompt",
                doctor_name=selected["doctor_name"],
                date=selected["date"],
                time=selected["time"],
            )
            trace("ACTION", session_id,
                  f"selection complete → confirming_cancel | "
                  f"appt_id={selected['appointment_id']!r}")

        return state

    # =========================================================================
    # CONFIRMING RESCHEDULE
    # =========================================================================

    async def _confirming_reschedule(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        appointment_id = memory.get("selected_appointment_id")
        doctor_name    = memory.get("selected_appointment_doctor", "")
        appt_date      = memory.get("selected_appointment_date", "")
        appt_time      = memory.get("selected_appointment_time", "")

        trace("ACTION", session_id,
              f"confirming_reschedule | appt_id={appointment_id!r} | "
              f"doctor={doctor_name!r} | date={appt_date!r} | time={appt_time!r}")

        if not appointment_id:
            trace("ACTION", session_id,
                  "GUARD FAILURE: appt_id=None at confirming_reschedule — "
                  "selected_appointment_index was never resolved")
            state.response = "No appointment selected. Please start again."
            memory["step"] = "idle"
            return state

        msg_lower = state.message.lower()
        if any(w in msg_lower for w in _NEGATIVE_WORDS):
            cleared = WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
            if cleared:
                await self.memory.delete_keys(state.session_id, cleared)
            memory["step"] = "idle"
            state.response = BookingResponses.get(language, "reschedule_aborted")
            trace("ACTION", session_id, "confirming_reschedule — user aborted")
            return state

        # User confirmed (yes / any non-negative reply).
        #
        # Check whether new_date / new_time are already in memory BEFORE
        # clearing anything.  Values extracted from the ORIGINAL reschedule
        # message ("reschedule appointment 1 to 27-05 at 11am") are written
        # to Redis by StateWriterNode and survive the confirmation turn.
        new_date = memory.get("new_date")
        new_time = memory.get("new_time")

        if new_date and new_time:
            # Both already known — skip date/time collection entirely
            memory["step"] = "ready_to_reschedule"
            trace("ACTION", session_id,
                  f"confirming_reschedule — new_date={new_date!r} new_time={new_time!r} "
                  f"both known → ready_to_reschedule")
            return await self._run(state)

        if new_date:
            # Date known — only time is missing
            memory["step"] = "awaiting_reschedule_time"
            trace("ACTION", session_id,
                  f"confirming_reschedule — new_date={new_date!r} known, "
                  f"new_time missing → awaiting_reschedule_time")
            return await self._run(state)

        # Neither known — clear any genuinely stale values left over from
        # a prior reschedule attempt that was aborted mid-collection, then
        # collect fresh date/time from the user.
        cleared = WorkflowStateCleaner.clear_reschedule_dates(memory, session_id)
        if cleared:
            await self.memory.delete_keys(state.session_id, cleared)
            trace("ACTION", session_id,
                  f"confirming_reschedule — cleared stale reschedule dates: {cleared}")

        memory["step"] = "awaiting_reschedule_date"
        state.response = BookingResponses.get(language, "ask_reschedule_date")
        trace("ACTION", session_id,
              "confirming_reschedule — confirmed → awaiting_reschedule_date")
        return state

    # =========================================================================
    # CONFIRMING CANCEL
    # =========================================================================

    async def _confirming_cancel(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        appointment_id = memory.get("selected_appointment_id")
        patient_id = state.patient_id or memory.get("patient_id")
        doctor_name = memory.get("selected_appointment_doctor", "")
        appt_date = memory.get("selected_appointment_date", "")
        appt_time = memory.get("selected_appointment_time", "")

        trace("ACTION", session_id,
              f"confirming_cancel | appt_id={appointment_id!r} | "
              f"doctor={doctor_name!r} | date={appt_date!r} | time={appt_time!r} | "
              f"patient={patient_id!r}")

        if not appointment_id:
            trace("ACTION", session_id,
                  "GUARD FAILURE: appt_id=None — selected_appointment_index was never "
                  "resolved against appointment_list (check WorkflowNode routing)")
            state.response = "No appointment selected. Please start again."
            memory["step"] = "idle"
            return state

        try:
            await self.tools.cancel_patient_appointment(appointment_id)
            state.response = BookingResponses.get(
                language, "cancel_success",
                doctor_name=doctor_name,
                date=appt_date,
            )
            memory["step"] = "completed"
            trace("ACTION", session_id, "cancel SUCCESS")

            # Clean up appointment selection state from memory + Redis
            cleared = WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
            if cleared:
                await self.memory.delete_keys(state.session_id, cleared)

            # Fire-and-forget: update patient profile
            asyncio.create_task(self.patient_memory.record_cancellation(
                patient_id=patient_id or "",
                appointment_id=appointment_id,
            ))
            asyncio.create_task(self.patient_memory.cancel_reminder(appointment_id))

        except Exception as exc:
            trace("ACTION", session_id, f"cancel FAILED: {exc}")
            state.response = "Cancellation failed. Please try again later."
            memory["step"] = "idle"

        return state

    # =========================================================================
    # AWAITING RESCHEDULE DATE
    # =========================================================================

    async def _awaiting_reschedule_date(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        if memory.get("new_date"):
            memory["step"] = "awaiting_reschedule_time"
            trace("ACTION", session_id,
                  f"awaiting_reschedule_date — new_date={memory['new_date']!r} → next step")
            return await self._run(state)

        # Availability exploration: user asked to see available slots instead of
        # providing a specific date ("show me available", "what slots do you have").
        if _is_availability_exploration(state.message):
            doctor_id = (
                memory.get("selected_appointment_doctor_id")
                or memory.get("doctor_id")
            )
            trace("ACTION", session_id,
                  f"awaiting_reschedule_date: availability exploration | "
                  f"doctor_id={doctor_id!r}")

            next_date: str | None = None
            valid_slots: list = []

            if doctor_id:
                try:
                    next_date = await self.next_available.find_next_date(doctor_id)
                except Exception as exc:
                    trace("ACTION", session_id, f"find_next_date ERROR: {exc!r}")

                if next_date:
                    try:
                        free_slots = await self.availability_service.get_free_slots(
                            doctor_id=doctor_id, date=next_date,
                        )
                        valid_slots = [
                            s for s in free_slots
                            if isinstance(s, dict) and s.get("start")
                        ]
                    except Exception as exc:
                        trace("ACTION", session_id, f"get_free_slots ERROR: {exc!r}")

            if valid_slots:
                # Pin the next available date so the slot-selection step only
                # needs to resolve new_time — date is already committed.
                memory["new_date"]        = next_date
                memory["suggested_slots"] = valid_slots
                memory["step"]            = "awaiting_reschedule_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "reschedule_next_available_slots",
                    date=next_date, slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"exploration → next_date={next_date!r} | "
                      f"{len(valid_slots)} slot(s) offered | "
                      f"step=awaiting_reschedule_slot_selection")
            else:
                state.response = BookingResponses.get(language, "reschedule_no_next_available")
                trace("ACTION", session_id,
                      "exploration — no next available date/slots found")
            return state

        state.response = BookingResponses.get(language, "ask_reschedule_date")
        trace("ACTION", session_id, "awaiting_reschedule_date — asking user")
        return state

    # =========================================================================
    # AWAITING RESCHEDULE TIME
    # =========================================================================

    async def _awaiting_reschedule_time(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        if memory.get("new_time"):
            # MODE 2 — soft pre-validation, mirrors booking's _awaiting_time:
            # confirm new_time is an actual free slot for new_date BEFORE
            # recursing into ready_to_reschedule.
            doctor_id = (
                memory.get("selected_appointment_doctor_id")
                or memory.get("doctor_id")
            )
            new_date = memory.get("new_date")
            proposed = memory.get("new_time")

            if doctor_id and new_date:
                try:
                    norm_proposed = TimeNormalizer.normalize(proposed)
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=doctor_id, date=new_date,
                    )
                    valid_slots = [
                        s for s in free_slots
                        if isinstance(s, dict) and s.get("start")
                    ]

                    if not valid_slots:
                        memory.pop("new_date", None)
                        memory.pop("new_time", None)
                        await self.memory.delete_keys(state.session_id, ["new_date", "new_time"])
                        memory["step"] = "awaiting_reschedule_date"
                        state.response = BookingResponses.get(
                            language, "reschedule_no_slots_for_date", date=new_date,
                        )
                        trace("ACTION", session_id,
                              f"MODE 2: free_slots empty for doctor={doctor_id!r} date={new_date!r} "
                              f"→ awaiting_reschedule_date")
                        return state

                    matched = SlotFormatter.match_typed_time(valid_slots, norm_proposed)
                    if not matched:
                        memory["suggested_slots"] = valid_slots
                        memory["step"]            = "awaiting_reschedule_slot_selection"
                        memory.pop("new_time", None)
                        await self.memory.delete_keys(state.session_id, ["new_time"])
                        slots_list = SlotFormatter.numbered_list(valid_slots, language)
                        state.response = BookingResponses.get(
                            language, "reschedule_slot_unavailable_with_alternatives",
                            requested_time=SlotFormatter.to_12h(proposed),
                            slots=slots_list,
                        )
                        trace("ACTION", session_id,
                              f"MODE 2: {proposed!r} not in available slots | "
                              f"{len(valid_slots)} alternative(s) → awaiting_reschedule_slot_selection")
                        return state

                    if matched != proposed:
                        memory["new_time"] = matched
                        trace("ACTION", session_id,
                              f"MODE 2: new_time canonicalized {proposed!r} → {matched!r}")
                except Exception as exc:
                    trace("ACTION", session_id,
                          f"MODE 2 pre-validation error: {exc!r} — "
                          f"proceeding to ready_to_reschedule without pre-validation")

            memory["step"] = "ready_to_reschedule"
            trace("ACTION", session_id,
                  f"awaiting_reschedule_time — new_time={memory['new_time']!r} → ready_to_reschedule")
            return await self._run(state)

        # Availability exploration: user asked to see available times for the
        # already-confirmed date ("show me available times", "what slots?").
        if _is_availability_exploration(state.message):
            doctor_id = (
                memory.get("selected_appointment_doctor_id")
                or memory.get("doctor_id")
            )
            new_date = memory.get("new_date")
            trace("ACTION", session_id,
                  f"awaiting_reschedule_time: availability exploration | "
                  f"doctor_id={doctor_id!r} new_date={new_date!r}")

            valid_slots: list = []

            if doctor_id and new_date:
                try:
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=doctor_id, date=new_date,
                    )
                    valid_slots = [
                        s for s in free_slots
                        if isinstance(s, dict) and s.get("start")
                    ]
                except Exception as exc:
                    trace("ACTION", session_id, f"get_free_slots ERROR: {exc!r}")

            if valid_slots:
                memory["suggested_slots"] = valid_slots
                memory["step"]            = "awaiting_reschedule_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "reschedule_time_slots",
                    date=new_date, slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"exploration → {len(valid_slots)} slot(s) for {new_date!r} | "
                      f"step=awaiting_reschedule_slot_selection")
            else:
                # Slots couldn't be fetched — fall through to the normal prompt
                state.response = BookingResponses.get(language, "ask_reschedule_time")
                trace("ACTION", session_id,
                      "exploration — no slots found, re-prompting for time")
            return state

        state.response = BookingResponses.get(language, "ask_reschedule_time")
        trace("ACTION", session_id, "awaiting_reschedule_time — asking user")
        return state

    # =========================================================================
    # READY TO RESCHEDULE
    # =========================================================================

    async def _ready_to_reschedule(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        appointment_id = memory.get("selected_appointment_id")
        doctor_id      = (
            memory.get("selected_appointment_doctor_id")
            or memory.get("doctor_id")
        )
        patient_id     = state.patient_id or memory.get("patient_id")
        new_date_raw   = memory.get("new_date")
        new_time_raw   = memory.get("new_time")

        trace("ACTION", session_id,
              f"ready_to_reschedule | appt={appointment_id!r} doctor_id={doctor_id!r} "
              f"new_date={new_date_raw!r} new_time={new_time_raw!r}")

        try:
            iso_date = DateNormalizer.normalize(new_date_raw)
            hm_time  = TimeNormalizer.normalize(new_time_raw)
        except ValueError as exc:
            trace("ACTION", session_id, f"reschedule normalization error: {exc}")
            if "date" in str(exc).lower():
                state.response = BookingResponses.get(language, "invalid_date")
                memory.pop("new_date", None)
                await self.memory.delete_keys(state.session_id, ["new_date"])
                memory["step"] = "awaiting_reschedule_date"
            else:
                state.response = BookingResponses.get(language, "invalid_time")
                memory.pop("new_time", None)
                await self.memory.delete_keys(state.session_id, ["new_time"])
                memory["step"] = "awaiting_reschedule_time"
            return state

        try:
            await self.tools.reschedule_appointment(
                appointment_id=appointment_id,
                payload={"date": f"{iso_date}T00:00:00", "time": hm_time},
            )
            state.response = BookingResponses.get(
                language, "reschedule_success",
                date=iso_date, time=hm_time,
            )
            memory["step"] = "completed"
            trace("ACTION", session_id,
                  f"reschedule SUCCESS → {iso_date} {hm_time}")

            # Clean up appointment + reschedule state from memory + Redis
            cleared = (
                WorkflowStateCleaner.clear_all_appointment_state(memory, session_id)
                + WorkflowStateCleaner.clear_reschedule_dates(memory, session_id)
            )
            if cleared:
                await self.memory.delete_keys(state.session_id, cleared)

            # Fire-and-forget: update patient profile + reschedule reminder
            asyncio.create_task(self.patient_memory.record_reschedule(
                patient_id=patient_id or "",
                appointment_id=appointment_id or "",
                new_date=iso_date,
                new_time=hm_time,
            ))
            asyncio.create_task(self.patient_memory.cancel_reminder(appointment_id or ""))
            advance_hours = state.profile.get("reminder_preferences", {}).get("advance_hours", 24)
            channel = state.profile.get("reminder_preferences", {}).get("channel", "app")
            asyncio.create_task(self.patient_memory.schedule_reminder(
                appointment_id=appointment_id or "",
                patient_id=patient_id or "",
                doctor_name=memory.get("selected_appointment_doctor", ""),
                appointment_date=iso_date,
                appointment_time=hm_time,
                advance_hours=advance_hours,
                channel=channel,
            ))

        except Exception as exc:
            # Reschedule failed — fetch free slots for the new date and offer
            # alternatives (mirrors the booking conflict-recovery pattern).
            requested_display = SlotFormatter.to_12h(hm_time)
            trace("ACTION", session_id,
                  f"reschedule FAILED: {exc!r} | "
                  f"requested slot: date={iso_date!r} time={hm_time!r} "
                  f"({requested_display})")

            free_slots: list = []
            if doctor_id:
                try:
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=doctor_id, date=iso_date,
                    )
                except Exception as avail_exc:
                    trace("ACTION", session_id,
                          f"free-slots lookup FAILED: {avail_exc!r}")

            valid_slots = [
                s for s in free_slots
                if isinstance(s, dict) and s.get("start")
            ]
            trace("ACTION", session_id,
                  f"reschedule conflict — valid alternatives: "
                  f"{[s['start'] for s in valid_slots]!r}")

            memory.pop("new_time", None)
            await self.memory.delete_keys(state.session_id, ["new_time"])

            if valid_slots:
                memory["suggested_slots"] = valid_slots
                memory["step"] = "awaiting_reschedule_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "reschedule_slot_unavailable_with_alternatives",
                    requested_time=requested_display,
                    slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"step → awaiting_reschedule_slot_selection | "
                      f"{len(valid_slots)} alternative(s) offered")
            else:
                memory.pop("new_date", None)
                await self.memory.delete_keys(state.session_id, ["new_date"])
                memory["step"] = "awaiting_reschedule_date"
                state.response = BookingResponses.get(
                    language, "reschedule_no_slots_for_date",
                    date=iso_date,
                )
                trace("ACTION", session_id,
                      "no alternatives — step → awaiting_reschedule_date")

        return state

    # =========================================================================
    # AWAITING RESCHEDULE SLOT SELECTION
    # Entered after ready_to_reschedule fails and free slots exist.
    # Mirrors awaiting_slot_selection but uses new_time and routes to
    # ready_to_reschedule instead of ready_to_book.
    # =========================================================================

    async def _awaiting_reschedule_slot_selection(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        suggested_slots = memory.get("suggested_slots", [])

        selected_index = (
            memory.get("selected_appointment_index")
            or memory.get("selected_doctor_index")
        )
        time_input = memory.get("new_time")

        trace("ACTION", session_id,
              f"awaiting_reschedule_slot_selection | index={selected_index} "
              f"time_input={time_input!r} | "
              f"{len(suggested_slots)} suggestion(s): "
              f"{[s.get('start') for s in suggested_slots]!r}")

        resolved_time: str | None = None

        if selected_index:
            resolved_time = SlotFormatter.pick_by_index(suggested_slots, selected_index)
            if resolved_time:
                trace("ACTION", session_id,
                      f"index selection: {selected_index} → {resolved_time!r}")

        if not resolved_time and time_input:
            try:
                normalized = TimeNormalizer.normalize(time_input)
                matched = SlotFormatter.match_typed_time(suggested_slots, normalized)
                resolved_time = matched or normalized
                trace("ACTION", session_id,
                      f"direct time input: {time_input!r} → "
                      f"normalized={normalized!r} | "
                      f"slot_match={'yes' if matched else 'no (accepted anyway)'}")
            except ValueError:
                trace("ACTION", session_id,
                      f"time input {time_input!r} could not be normalized")

        if not resolved_time:
            if suggested_slots:
                slots_list = SlotFormatter.numbered_list(suggested_slots, language)
                state.response = BookingResponses.get(
                    language, "reschedule_slot_reselect_prompt", slots=slots_list
                )
                trace("ACTION", session_id,
                      "no valid selection — re-showing reschedule slot list")
            else:
                memory.pop("new_date", None)
                await self.memory.delete_keys(state.session_id, ["new_date"])
                memory["step"] = "awaiting_reschedule_date"
                state.response = BookingResponses.get(language, "ask_reschedule_date")
                trace("ACTION", session_id,
                      "suggested_slots empty — falling back to awaiting_reschedule_date")
            return state

        memory["new_time"] = resolved_time
        memory.pop("suggested_slots", None)
        memory.pop("selected_appointment_index", None)
        memory.pop("selected_doctor_index", None)
        await self.memory.delete_keys(state.session_id, ["suggested_slots"])

        trace("ACTION", session_id,
              f"reschedule slot resolved: {resolved_time!r} | "
              f"display={SlotFormatter.to_12h(resolved_time)!r} | "
              f"step → ready_to_reschedule")

        memory["step"] = "ready_to_reschedule"
        return await self._run(state)

    # =========================================================================
    # SAVE REMINDER PREFERENCE
    # =========================================================================

    async def _saving_reminder_preference(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        hours = memory.get("reminder_hours")
        patient_id = state.patient_id or memory.get("patient_id")

        trace("ACTION", session_id, f"saving_reminder_preference | hours={hours!r}")

        if not hours or not isinstance(hours, int) or hours < 1:
            state.response = BookingResponses.get(language, "reminder_invalid")
            return state

        channel = state.profile.get("reminder_preferences", {}).get("channel", "app")

        # Fire-and-forget: persist preference to MongoDB
        asyncio.create_task(self.patient_memory.update_reminder_preference(
            patient_id=patient_id or "",
            advance_hours=hours,
            channel=channel,
        ))

        state.response = BookingResponses.get(language, "reminder_saved", hours=hours)
        memory["step"] = "completed"
        trace("ACTION", session_id, f"reminder preference saved: {hours}h via {channel}")
        return state

    # =========================================================================
    # READY TO CANCEL (legacy path — no appointment_id known)
    # =========================================================================

    async def _ready_to_cancel(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        trace("ACTION", session_id, "ready_to_cancel (no appointment_id) — fetching list")
        memory["pending_action"] = "cancel"
        memory["step"] = "fetching_appointments"
        return await self._run(state)
