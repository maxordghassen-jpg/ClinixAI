"""
Booking workflow handler.

Covers all steps from doctor search through confirmed booking, plus the
slot-conflict recovery flow.

Steps owned:
    searching_doctors, awaiting_specialty, doctor_selected,
    ready_to_book, awaiting_date, awaiting_time,
    awaiting_slot_selection, awaiting_recovery_choice
"""
from __future__ import annotations

import asyncio
from typing import Any, Callable, Coroutine

from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.booking_responses import BookingResponses
from graphs.shared.workflow_state_cleaner import WorkflowStateCleaner
from graphs.shared.slot_formatter import SlotFormatter
from graphs.shared.normalizers.time_normalizer import TimeNormalizer

from graphs.patient.handlers.helpers import (
    _AFFIRMATIVE_WORDS,
    _is_availability_exploration,
    _RECOVERY_KEYWORDS,
)

# Steps this handler owns — used by ActionNode to route.
STEPS: frozenset[str] = frozenset({
    "searching_doctors",
    "awaiting_specialty",
    "doctor_selected",
    "ready_to_book",
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",
    "awaiting_recovery_choice",
})


class BookingHandler:
    """Handles all patient booking workflow steps."""

    def __init__(
        self,
        *,
        tools: Any,
        redis_memory: Any,
        booking_service: Any,
        availability_service: Any,
        next_available: Any,
        doctor_service: Any,
        patient_memory: Any,
        responses: Any,
        run_fn: Callable[[AgentState], Coroutine[Any, Any, AgentState]],
    ) -> None:
        self.tools = tools
        self.memory = redis_memory
        self.booking_service = booking_service
        self.availability_service = availability_service
        self.next_available = next_available
        self.doctor_service = doctor_service
        self.patient_memory = patient_memory
        self.responses = responses
        self._run = run_fn  # ActionNode.run — for cross-step re-dispatch

    async def handle(self, state: AgentState) -> AgentState:
        step = state.memory.get("step")
        if step == "searching_doctors":
            return await self._searching_doctors(state)
        if step == "awaiting_specialty":
            return await self._awaiting_specialty(state)
        if step == "doctor_selected":
            return await self._doctor_selected(state)
        if step == "ready_to_book":
            return await self._ready_to_book(state)
        if step == "awaiting_date":
            return await self._awaiting_date(state)
        if step == "awaiting_time":
            return await self._awaiting_time(state)
        if step == "awaiting_slot_selection":
            return await self._awaiting_slot_selection(state)
        if step == "awaiting_recovery_choice":
            return await self._awaiting_recovery_choice(state)
        return state

    async def handle_direct_recovery(self, state: AgentState) -> AgentState:
        """Catch-all when intent==booking but step is not a known booking step."""
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        trace("ACTION", session_id, "direct booking recovery path")

        if (
            not memory.get("doctor_id")
            and memory.get("selected_doctor_index")
            and memory.get("doctor_results")
        ):
            doctors = memory.get("doctor_results", [])
            position = memory.get("selected_doctor_index") - 1
            if 0 <= position < len(doctors):
                selected = doctors[position]
                memory["doctor_id"] = str(selected.get("id"))
                memory["doctor_name"] = selected.get("name")
                trace("ACTION", session_id,
                      f"recovered doctor: {memory['doctor_name']!r}")

        if memory.get("doctor_id") and memory.get("date") and memory.get("time"):
            memory["step"] = "ready_to_book"
            return await self._run(state)

        # Personalization: suggest usual doctor if profile has one
        profile_doctors = state.profile.get("preferred_doctors", [])
        profile_specialties = state.profile.get("preferred_specialties", [])
        if profile_doctors and profile_specialties:
            last_doc = profile_doctors[-1]
            state.response = BookingResponses.get(
                language, "suggest_usual_doctor",
                name=last_doc.get("name", ""),
                specialty=profile_specialties[0] if profile_specialties else "",
            )
        else:
            state.response = "How can I help you today?"
        trace("ACTION", session_id, "booking recovery — incomplete context")
        return state

    # =========================================================================
    # SEARCH DOCTORS
    # =========================================================================

    async def _searching_doctors(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        # Resolution priority: explicit query → doctor name (entity resolution) → specialty
        query = memory.get("query") or memory.get("doctor_name") or memory.get("specialty")
        trace("ACTION", session_id, f"searching doctors | query={query!r}")

        # Freshness-aware stale cleanup: remove scheduling fields the user
        # did NOT supply in this message (e.g. stale date/time from a prior
        # session).  Fields present in extracted_this_turn are kept — they
        # were just parsed and are authoritative.
        fresh = getattr(state, "extracted_this_turn", set())
        trace("ACTION", session_id,
              f"searching_doctors | extracted_this_turn={sorted(fresh)} | "
              f"memory before cleanup: date={memory.get('date')!r} "
              f"time={memory.get('time')!r}")
        cleared = WorkflowStateCleaner.clear_stale_scheduling(memory, fresh, session_id)
        if cleared:
            await self.memory.delete_keys(state.session_id, cleared)
            trace("ACTION", session_id,
                  f"stale scheduling fields cleared + synced to Redis: {cleared}")

        try:
            doctors = await self.doctor_service.search(query)
        except Exception as exc:
            trace("ACTION", session_id, f"doctor search ERROR: {exc}")
            state.response = "Doctor search is temporarily unavailable. Please try again in a moment."
            return state

        if not doctors:
            trace("ACTION", session_id, f"no doctors found for {query!r}")
            state.response = f"No doctors found for {query}."
            return state

        trace("ACTION", session_id, f"found {len(doctors)} doctor(s)")

        doctor_results = [
            {"id": d.get("id"), "name": d.get("name"), "address": d.get("address")}
            for d in doctors[:5]
        ]
        memory["doctor_results"] = doctor_results
        memory["step"] = "selecting_doctor"

        # Checkpoint — persist before waiting for user selection
        await self.memory.update(
            state.session_id,
            {"doctor_results": doctor_results, "step": "selecting_doctor"},
        )
        trace("ACTION", session_id,
              f"checkpoint saved: {len(doctor_results)} doctors, step=selecting_doctor")

        if len(doctors) == 1:
            doctor = doctors[0]
            memory["doctor_id"] = str(doctor.get("id"))
            memory["doctor_name"] = doctor.get("name")
            memory["intent"] = "booking"
            trace("ACTION", session_id,
                  f"single doctor auto-selected: {memory['doctor_name']!r}")
            if not memory.get("date"):
                memory["step"] = "awaiting_date"
                state.response = (
                    BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                    + "\n\n" + BookingResponses.get(language, "ask_date")
                )
            elif not memory.get("time"):
                memory["step"] = "awaiting_time"
                state.response = (
                    BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                    + "\n\n" + BookingResponses.get(language, "ask_time")
                )
            else:
                memory["step"] = "ready_to_book"
                return await self._run(state)
            return state

        formatted = [
            f"{i}. {d.get('name')} - {d.get('address')}"
            for i, d in enumerate(doctors[:5], start=1)
        ]
        state.response = (
            BookingResponses.get(language, "doctors_found")
            + "\n\n" + "\n".join(formatted)
            + "\n\n" + BookingResponses.get(language, "doctor_prompt")
        )
        return state

    # =========================================================================
    # AWAITING SPECIALTY
    # =========================================================================

    async def _awaiting_specialty(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        specialty = memory.get("specialty")
        if specialty:
            memory["step"] = "searching_doctors"
            trace("ACTION", session_id,
                  f"awaiting_specialty — specialty={specialty!r} → recursing")
            return await self._run(state)

        # Personalization: suggest from profile if available
        profile_specialties = state.profile.get("preferred_specialties", [])
        if profile_specialties:
            hint = f" (e.g. '{profile_specialties[0]}')" if language == "english" else ""
            state.response = BookingResponses.get(language, "ask_specialty") + hint
        else:
            state.response = BookingResponses.get(language, "ask_specialty")
        trace("ACTION", session_id, "awaiting_specialty — asking user")
        return state

    # =========================================================================
    # DOCTOR SELECTED
    # =========================================================================

    async def _doctor_selected(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        doctors = memory.get("doctor_results", [])
        selected_index = memory.get("selected_doctor_index", 1)
        position = selected_index - 1

        trace("ACTION", session_id,
              f"doctor_selected | index={selected_index} | {len(doctors)} available")

        if not doctors:
            # doctor_results was evicted from Redis or never written
            # (e.g. session restart mid-flow, StateWriterNode filtered out
            # an empty list, or checkpoint write failed after step was saved).
            # Re-search rather than trapping the user in an unresolvable step.
            memory["step"] = "searching_doctors"
            trace("ACTION", session_id,
                  "doctor_selected — doctor_results empty, re-routing to searching_doctors")
            return await self._run(state)

        if position < 0 or position >= len(doctors):
            trace("ACTION", session_id,
                  f"invalid selection: position={position} out of range")
            state.response = BookingResponses.get(language, "invalid_selection")
            return state

        doctor = doctors[position]
        memory["doctor_id"] = str(doctor.get("id"))
        memory["doctor_name"] = doctor.get("name")
        memory["intent"] = "booking"
        trace("ACTION", session_id,
              f"doctor confirmed: id={memory['doctor_id']} name={memory['doctor_name']!r}")

        # ── Scheduling cache reset ───────────────────────────────────────────
        # Preserve date/time: any stale cross-session values were already
        # cleared by searching_doctors at the start of this workflow.
        # date/time in memory at this point are valid — either extracted
        # earlier in this session ("I want a dentist tomorrow at 9") or
        # absent.  Clear only the derived/cached scheduling fields (normalized
        # forms, slot lists, etc.) because those always belong to the old
        # doctor and must be regenerated for the newly selected one.
        cleared = WorkflowStateCleaner.clear_stale_scheduling(
            memory,
            fresh_fields={"date", "time"},  # treat raw date/time as always valid here
            session_id=session_id,
        )
        if cleared:
            await self.memory.delete_keys(state.session_id, cleared)
            trace("ACTION", session_id,
                  f"cache fields cleared for new doctor: {cleared}")

        # Clear doctor selection artifacts — consumed after resolution.
        # Leaving selected_doctor_index in Redis risks it being mis-read
        # as a slot index inside awaiting_slot_selection (both fields are
        # checked as fallbacks there).  doctor_results is a large payload
        # that has no use after the doctor is confirmed.
        memory.pop("doctor_results", None)
        memory.pop("selected_doctor_index", None)
        await self.memory.delete_keys(
            state.session_id, ["doctor_results", "selected_doctor_index"]
        )
        trace("ACTION", session_id,
              "cleared doctor selection artifacts: doctor_results, selected_doctor_index")

        trace("ACTION", session_id,
              f"post-cleanup: date={memory.get('date')!r} "
              f"time={memory.get('time')!r}")

        # Route based on what is already known — skip collection steps
        # when the user provided date/time in the same message.
        if not memory.get("date"):
            memory["step"] = "awaiting_date"
            trace("ACTION", session_id,
                  f"doctor_selected → awaiting_date | "
                  f"doctor={memory['doctor_id']!r} name={memory['doctor_name']!r}")
            state.response = (
                BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                + "\n\n" + BookingResponses.get(language, "ask_date")
            )
        elif not memory.get("time"):
            memory["step"] = "awaiting_time"
            trace("ACTION", session_id,
                  f"doctor_selected → awaiting_time (date={memory['date']!r} known) | "
                  f"doctor={memory['doctor_id']!r}")
            state.response = (
                BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                + "\n\n" + BookingResponses.get(language, "ask_time")
            )
        else:
            memory["step"] = "ready_to_book"
            trace("ACTION", session_id,
                  f"doctor_selected → ready_to_book "
                  f"(date={memory['date']!r} time={memory['time']!r} both known) | "
                  f"doctor={memory['doctor_id']!r}")
            return await self._run(state)

        return state

    # =========================================================================
    # READY TO BOOK
    # =========================================================================

    async def _ready_to_book(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        doctor_id = memory.get("doctor_id")
        patient_id = state.patient_id or memory.get("patient_id")
        date = memory.get("date")
        booking_time = memory.get("time")

        trace("ACTION", session_id,
              f"booking attempt | doctor={doctor_id} patient={patient_id} "
              f"date={date!r} time={booking_time!r}")

        try:
            result = await self.booking_service.book(
                doctor_id=doctor_id,
                patient_id=patient_id,
                date=date,
                time=booking_time,
            )
            appointment_id = (result or {}).get("id", "") if isinstance(result, dict) else ""

            state.response = BookingResponses.get(language, "booking_success")
            memory["step"] = "completed"
            trace("ACTION", session_id, f"booking SUCCESS — step=completed appt_id={appointment_id}")

            # ── Fire-and-forget: record booking in patient profile ──────
            advance_hours = state.profile.get("reminder_preferences", {}).get("advance_hours", 24)
            channel = state.profile.get("reminder_preferences", {}).get("channel", "app")
            asyncio.create_task(self.patient_memory.record_booking(
                patient_id=patient_id or "",
                appointment_id=appointment_id,
                doctor_id=doctor_id or "",
                doctor_name=memory.get("doctor_name", ""),
                specialty=memory.get("specialty", ""),
                date=date or "",
                time=booking_time or "",
            ))
            if appointment_id:
                asyncio.create_task(self.patient_memory.schedule_reminder(
                    appointment_id=appointment_id,
                    patient_id=patient_id or "",
                    doctor_name=memory.get("doctor_name", ""),
                    appointment_date=date or "",
                    appointment_time=booking_time or "",
                    advance_hours=advance_hours,
                    channel=channel,
                ))
            # ── Fire-and-forget: update language in profile ────────────
            if language and patient_id:
                profile_lang = state.profile.get("language", "")
                if language != profile_lang:
                    asyncio.create_task(
                        self.patient_memory.update_language(patient_id, language)
                    )

        except ValueError as exc:
            trace("ACTION", session_id, f"normalization error: {exc}")
            if "date" in str(exc).lower():
                state.response = BookingResponses.get(language, "invalid_date")
                memory.pop("date", None)
                await self.memory.delete_keys(state.session_id, ["date"])
                memory["step"] = "awaiting_date"
            else:
                state.response = BookingResponses.get(language, "invalid_time")
                memory.pop("time", None)
                await self.memory.delete_keys(state.session_id, ["time"])
                memory["step"] = "awaiting_time"

        except Exception as exc:
            # ── Slot conflict recovery ────────────────────────────────────
            # The booking attempt failed (typically a 409 conflict — slot
            # already booked or not configured for this doctor/day).
            # Fetch available slots for the same date so we can offer
            # concrete alternatives rather than a bare error message.
            #
            # Recovery paths:
            #   A. Alternatives exist  → store in suggested_slots, set
            #      step=awaiting_slot_selection, show numbered list.
            #   B. No alternatives     → clear the dead date, set
            #      step=awaiting_date, ask the user to try another day.
            #
            # Always clear the conflicting time from memory and Redis so
            # it cannot accidentally re-trigger a booking with a bad slot.
            requested_display = SlotFormatter.to_12h(booking_time or "")
            trace("ACTION", session_id,
                  f"booking FAILED: {exc!r} | "
                  f"requested slot: date={date!r} time={booking_time!r} "
                  f"({requested_display})")

            try:
                free_slots = await self.availability_service.get_free_slots(
                    doctor_id=doctor_id, date=date,
                )
            except Exception as avail_exc:
                trace("ACTION", session_id,
                      f"free-slots lookup FAILED: {avail_exc!r}")
                free_slots = []

            trace("ACTION", session_id,
                  f"free-slots raw: count={len(free_slots)} | data={free_slots!r}")

            valid_slots = [
                s for s in free_slots
                if isinstance(s, dict) and s.get("start")
            ]
            trace("ACTION", session_id,
                  f"valid alternatives: {[s['start'] for s in valid_slots]!r}")

            keys_to_delete = ["time"]

            if valid_slots:
                # Path A — offer alternatives, wait for selection
                memory["suggested_slots"] = valid_slots
                memory["step"] = "awaiting_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "slot_unavailable_with_alternatives",
                    requested_time=requested_display,
                    slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"step → awaiting_slot_selection | "
                      f"{len(valid_slots)} alternative(s) offered: "
                      f"{[s['start'] for s in valid_slots]!r}")
            else:
                # Path B — no slots for this date; enter guided recovery menu.
                failed_date = date or ""
                memory["recovery_context"] = {
                    "doctor_id":   doctor_id or "",
                    "doctor_name": memory.get("doctor_name", ""),
                    "failed_date": failed_date,
                    "specialty":   memory.get("specialty", ""),
                }
                memory.pop("date", None)
                keys_to_delete.append("date")
                memory["step"] = "awaiting_recovery_choice"
                state.response = BookingResponses.get(
                    language, "recovery_options",
                    date=failed_date,
                    doctor_name=memory.get("doctor_name", ""),
                )
                trace("ACTION", session_id,
                      f"no alternatives — step → awaiting_recovery_choice | "
                      f"recovery_context={memory['recovery_context']!r}")

            memory.pop("time", None)
            await self.memory.delete_keys(state.session_id, keys_to_delete)
            trace("ACTION", session_id,
                  f"stale keys deleted from Redis: {keys_to_delete!r}")

        return state

    # =========================================================================
    # AWAITING DATE
    # =========================================================================

    async def _awaiting_date(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        if memory.get("date"):
            memory["step"] = "awaiting_time"
            trace("ACTION", session_id,
                  f"awaiting_date — date={memory['date']!r} → recursing to awaiting_time")
            return await self._run(state)

        # MODE 1 — availability exploration.
        # User wants to SEE upcoming slots rather than propose a specific
        # date.  Fetch the next available date + its free slots, embed the
        # date into each slot dict so SlotFormatter renders "date — time",
        # then route to awaiting_slot_selection (existing handler, no new
        # state or steps required).
        if _is_availability_exploration(state.message):
            doctor_id = memory.get("doctor_id")
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
                            {**s, "date": next_date}
                            for s in free_slots
                            if isinstance(s, dict) and s.get("start")
                        ]
                    except Exception as exc:
                        trace("ACTION", session_id, f"get_free_slots ERROR: {exc!r}")

            if valid_slots:
                memory["date"]            = next_date
                memory["suggested_slots"] = valid_slots
                memory["step"]            = "awaiting_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "next_available_slots",
                    doctor_name=memory.get("doctor_name", ""),
                    slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"MODE 1: next_date={next_date!r} | "
                      f"{len(valid_slots)} slot(s) → awaiting_slot_selection")
            else:
                state.response = BookingResponses.get(language, "no_next_available")
                trace("ACTION", session_id, "MODE 1: no next available slots found")
            return state

        state.response = BookingResponses.get(language, "ask_date")
        trace("ACTION", session_id, "awaiting_date — asking user")
        return state

    # =========================================================================
    # AWAITING TIME
    # =========================================================================

    async def _awaiting_time(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        if memory.get("time"):
            # MODE 2 — soft pre-validation.
            # Check whether the proposed time exists in the doctor's free
            # slots for this date BEFORE attempting the booking POST.
            # Avoids the round-trip of POST → 409 → fetch alternatives for
            # the common case of a user typing a time that has no slot.
            # Falls through silently on any service or normalization error
            # so the existing 409 recovery path still handles edge cases.
            doctor_id = memory.get("doctor_id")
            date      = memory.get("date")
            proposed  = memory.get("time")

            if doctor_id and date:
                try:
                    norm_proposed = TimeNormalizer.normalize(proposed)
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=doctor_id, date=date,
                    )
                    valid_slots = [
                        s for s in free_slots
                        if isinstance(s, dict) and s.get("start")
                    ]
                    if valid_slots:
                        matched = SlotFormatter.match_typed_time(valid_slots, norm_proposed)
                        if not matched:
                            # Proposed time is not in the configured slots.
                            # Surface alternatives now — no booking attempt needed.
                            memory["suggested_slots"] = valid_slots
                            memory["step"]            = "awaiting_slot_selection"
                            memory.pop("time", None)
                            await self.memory.delete_keys(state.session_id, ["time"])
                            slots_list = SlotFormatter.numbered_list(valid_slots, language)
                            state.response = BookingResponses.get(
                                language, "slot_unavailable_with_alternatives",
                                requested_time=SlotFormatter.to_12h(proposed),
                                slots=slots_list,
                            )
                            trace("ACTION", session_id,
                                  f"MODE 2: {proposed!r} not in available slots | "
                                  f"{len(valid_slots)} alternative(s) → awaiting_slot_selection")
                            return state
                        # Exact match — canonicalize the time to the slot's
                        # start value so downstream normalization succeeds.
                        if matched != proposed:
                            memory["time"] = matched
                            trace("ACTION", session_id,
                                  f"MODE 2: time canonicalized {proposed!r} → {matched!r}")
                except Exception as exc:
                    trace("ACTION", session_id,
                          f"MODE 2 pre-validation error: {exc!r} — "
                          f"proceeding to ready_to_book without pre-validation")

            memory["step"] = "ready_to_book"
            trace("ACTION", session_id,
                  f"awaiting_time — time={memory['time']!r} → recursing to ready_to_book")
            return await self._run(state)

        # MODE 1 — availability exploration.
        # User wants to SEE available times for the already-confirmed date.
        if _is_availability_exploration(state.message):
            doctor_id = memory.get("doctor_id")
            date      = memory.get("date")
            valid_slots: list = []

            if doctor_id and date:
                try:
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=doctor_id, date=date,
                    )
                    valid_slots = [
                        s for s in free_slots
                        if isinstance(s, dict) and s.get("start")
                    ]
                except Exception as exc:
                    trace("ACTION", session_id, f"get_free_slots ERROR: {exc!r}")

            if valid_slots:
                memory["suggested_slots"] = valid_slots
                memory["step"]            = "awaiting_slot_selection"
                slots_list = SlotFormatter.numbered_list(valid_slots, language)
                state.response = BookingResponses.get(
                    language, "time_slots_for_date",
                    date=date, slots=slots_list,
                )
                trace("ACTION", session_id,
                      f"MODE 1 (time): {len(valid_slots)} slot(s) for {date!r} → "
                      f"awaiting_slot_selection")
            else:
                state.response = BookingResponses.get(language, "ask_time")
                trace("ACTION", session_id,
                      "MODE 1 (time): no slots found, re-prompting for time")
            return state

        state.response = BookingResponses.get(language, "ask_time")
        trace("ACTION", session_id, "awaiting_time — asking user")
        return state

    # =========================================================================
    # AWAITING SLOT SELECTION
    # Entered after a 409 conflict where alternative slots exist.
    # Accepts either:
    #   • index-based reply ("the first one", "2")  → selected_appointment_index
    #   • direct time input ("10am", "10:30")        → time field
    # =========================================================================

    async def _awaiting_slot_selection(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        suggested_slots = memory.get("suggested_slots", [])

        # LLM may produce either field depending on phrasing
        selected_index = (
            memory.get("selected_appointment_index")
            or memory.get("selected_doctor_index")
        )
        time_input = memory.get("time")

        trace("ACTION", session_id,
              f"awaiting_slot_selection | index={selected_index} "
              f"time_input={time_input!r} | "
              f"{len(suggested_slots)} suggestion(s) available: "
              f"{[s.get('start') for s in suggested_slots]!r}")

        resolved_time: str | None = None

        # ── Strategy 1: index selection ───────────────────────────────────
        if selected_index:
            resolved_time = SlotFormatter.pick_by_index(suggested_slots, selected_index)
            if resolved_time:
                trace("ACTION", session_id,
                      f"index selection: {selected_index} → {resolved_time!r}")
            else:
                trace("ACTION", session_id,
                      f"index {selected_index} out of range "
                      f"(max {len(suggested_slots)}) — falling through to time input")

        # ── Strategy 2: direct time input ─────────────────────────────────
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
                      f"time input {time_input!r} could not be normalized — "
                      "re-showing options")

        # ── No resolution — re-show options ───────────────────────────────
        if not resolved_time:
            if suggested_slots:
                slots_list = SlotFormatter.numbered_list(suggested_slots, language)
                state.response = BookingResponses.get(
                    language, "slot_reselect_prompt", slots=slots_list
                )
                trace("ACTION", session_id, "no valid selection — re-showing slot list")
            else:
                # Slots expired or lost — fall back to asking for a new date
                memory["step"] = "awaiting_date"
                state.response = BookingResponses.get(language, "ask_date")
                trace("ACTION", session_id,
                      "suggested_slots empty — falling back to awaiting_date")
            return state

        # ── Slot resolved — proceed to booking ────────────────────────────
        memory["time"] = resolved_time

        # Clean up transient selection state
        memory.pop("suggested_slots", None)
        memory.pop("selected_appointment_index", None)
        memory.pop("selected_doctor_index", None)
        await self.memory.delete_keys(state.session_id, ["suggested_slots"])

        trace("ACTION", session_id,
              f"slot resolved: {resolved_time!r} | "
              f"display={SlotFormatter.to_12h(resolved_time)!r} | "
              f"step → ready_to_book")

        memory["step"] = "ready_to_book"
        return await self._run(state)

    # =========================================================================
    # AWAITING RECOVERY CHOICE
    # Entered after Path B (no slots + no alternatives).
    # Presents 4 guided options; resolves choice deterministically
    # using index → affirmative word → keyword scan, no LLM.
    # =========================================================================

    async def _awaiting_recovery_choice(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        recovery_ctx = memory.get("recovery_context", {})
        rc_doctor_id   = recovery_ctx.get("doctor_id",   memory.get("doctor_id", ""))
        rc_doctor_name = recovery_ctx.get("doctor_name", memory.get("doctor_name", ""))
        rc_specialty   = recovery_ctx.get("specialty",   memory.get("specialty", ""))

        # ── Resolve user's choice ─────────────────────────────────────────
        choice: int | None = None

        raw_index = (
            memory.get("selected_doctor_index")
            or memory.get("selected_appointment_index")
        )
        if raw_index and 1 <= int(raw_index) <= 4:
            choice = int(raw_index)
            trace("ACTION", session_id,
                  f"recovery: index selection → choice {choice}")
        else:
            msg_lower = state.message.lower()
            if any(w in msg_lower for w in _AFFIRMATIVE_WORDS):
                choice = 1
                trace("ACTION", session_id,
                      "recovery: affirmative word → choice 1 (try date)")
            else:
                for keywords, choice_num in _RECOVERY_KEYWORDS:
                    if any(kw in msg_lower for kw in keywords):
                        choice = choice_num
                        trace("ACTION", session_id,
                              f"recovery: keyword match → choice {choice_num}")
                        break

        trace("ACTION", session_id,
              f"awaiting_recovery_choice | choice={choice!r} | "
              f"doctor={rc_doctor_id!r} specialty={rc_specialty!r}")

        # ── Route to chosen recovery path ─────────────────────────────────

        if choice == 1:
            # Try a different date — re-enter booking at date collection
            memory.pop("date", None)
            memory.pop("time", None)
            memory.pop("recovery_context", None)
            await self.memory.delete_keys(state.session_id, ["date", "time", "recovery_context"])
            memory["step"] = "awaiting_date"
            state.response = BookingResponses.get(language, "recovery_try_date")
            trace("ACTION", session_id,
                  "recovery path 1 — try different date | step=awaiting_date")

        elif choice == 2:
            # Next available appointment — scan forward for a free date, then
            # fetch its actual slots so the user picks a concrete slot rather
            # than guessing a time that may not exist.
            memory.pop("recovery_context", None)
            await self.memory.delete_keys(state.session_id, ["recovery_context"])
            trace("ACTION", session_id,
                  f"recovery path 2 — next available | doctor={rc_doctor_id!r}")
            try:
                next_date = await self.next_available.find_next_date(rc_doctor_id)
            except Exception as exc:
                trace("ACTION", session_id, f"next_available ERROR: {exc}")
                next_date = None

            if next_date:
                try:
                    free_slots = await self.availability_service.get_free_slots(
                        doctor_id=rc_doctor_id, date=next_date,
                    )
                except Exception as exc:
                    trace("ACTION", session_id, f"free-slots ERROR: {exc!r}")
                    free_slots = []

                # Embed the date into each slot so SlotFormatter can render
                # "2026-05-25 — 9:00 AM" instead of a bare time.
                valid_slots = [
                    {**s, "date": next_date}
                    for s in free_slots
                    if isinstance(s, dict) and s.get("start")
                ]
                trace("ACTION", session_id,
                      f"next available: {next_date!r} | "
                      f"{len(valid_slots)} slot(s): "
                      f"{[s['start'] for s in valid_slots]!r}")

                if valid_slots:
                    memory["date"]            = next_date
                    memory["suggested_slots"] = valid_slots
                    memory["step"]            = "awaiting_slot_selection"
                    slots_list = SlotFormatter.numbered_list(valid_slots, language)
                    state.response = BookingResponses.get(
                        language, "recovery_next_available_slots",
                        doctor_name=rc_doctor_name,
                        slots=slots_list,
                    )
                    trace("ACTION", session_id,
                          f"step → awaiting_slot_selection | "
                          f"{len(valid_slots)} slot(s) offered for {next_date!r}")
                else:
                    # Date found but slot fetch returned nothing — fall back to
                    # the original date-only path so the user can still proceed.
                    memory["date"] = next_date
                    memory["step"] = "awaiting_time"
                    state.response = BookingResponses.get(
                        language, "recovery_next_available",
                        doctor_name=rc_doctor_name,
                        date=next_date,
                    )
                    trace("ACTION", session_id,
                          f"next available: {next_date!r} | "
                          f"no slot data — falling back to awaiting_time")
            else:
                # No upcoming slot — re-show trimmed menu (option 2 removed)
                state.response = BookingResponses.get(
                    language, "recovery_no_next_available",
                    doctor_name=rc_doctor_name,
                )
                trace("ACTION", session_id,
                      "no next available found — re-showing trimmed recovery menu")

        elif choice == 3:
            # Choose a different doctor — reset booking state, keep specialty
            cleared = WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
            memory.pop("recovery_context", None)
            cleared.append("recovery_context")
            await self.memory.delete_keys(state.session_id, cleared)
            if rc_specialty:
                memory["specialty"] = rc_specialty
                memory["step"] = "searching_doctors"
            else:
                memory["step"] = "awaiting_specialty"
            state.response = BookingResponses.get(
                language, "recovery_searching_doctor",
                specialty=rc_specialty or "doctor",
            )
            trace("ACTION", session_id,
                  f"recovery path 3 — new doctor | specialty={rc_specialty!r} | "
                  f"step={memory['step']!r}")
            return await self._run(state)

        elif choice == 4:
            # Find nearby — transition to geo search flow
            cleared = WorkflowStateCleaner.clear_full_booking_state(memory, session_id)
            memory.pop("recovery_context", None)
            cleared.append("recovery_context")
            await self.memory.delete_keys(state.session_id, cleared)
            memory["query"] = rc_specialty or "doctor"
            memory["intent"] = "geo_search"
            memory["step"] = "searching_places"
            state.response = BookingResponses.get(
                language, "recovery_searching_nearby",
                specialty=rc_specialty or "doctor",
            )
            trace("ACTION", session_id,
                  f"recovery path 4 — nearby | query={memory['query']!r}")
            return await self._run(state)

        else:
            # Unrecognized input — re-display the menu
            state.response = BookingResponses.get(language, "recovery_choice_invalid")
            trace("ACTION", session_id,
                  "recovery choice unrecognized — re-displaying menu")

        return state
