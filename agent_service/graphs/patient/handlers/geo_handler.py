"""
Geo search workflow handler.

Covers medical place search and selection, which can then transition
into the booking flow.

Steps owned:
    searching_places, selecting_place
"""
from __future__ import annotations

from typing import Any, Callable, Coroutine

from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.booking_responses import BookingResponses
from graphs.shared.workflow_state_cleaner import WorkflowStateCleaner

# Steps this handler owns — used by ActionNode to route.
STEPS: frozenset[str] = frozenset({
    "searching_places",
    "selecting_place",
})


class GeoHandler:
    """Handles geographic medical place search and selection."""

    def __init__(
        self,
        *,
        tools: Any,
        redis_memory: Any,
        responses: Any,
        run_fn: Callable[[AgentState], Coroutine[Any, Any, AgentState]],
    ) -> None:
        self.tools = tools
        self.memory = redis_memory
        self.responses = responses
        self._run = run_fn

    async def handle(self, state: AgentState) -> AgentState:
        step = state.memory.get("step")
        if step == "searching_places":
            return await self._searching_places(state)
        if step == "selecting_place":
            return await self._selecting_place(state)
        return state

    # =========================================================================
    # SEARCH PLACES
    # =========================================================================

    async def _searching_places(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        query = memory.get("query") or memory.get("specialty")
        trace("ACTION", session_id, f"searching places | query={query!r}")

        # Same freshness-aware stale cleanup as searching_doctors.
        fresh = getattr(state, "extracted_this_turn", set())
        trace("ACTION", session_id,
              f"searching_places | extracted_this_turn={sorted(fresh)} | "
              f"memory before cleanup: date={memory.get('date')!r} "
              f"time={memory.get('time')!r}")
        cleared = WorkflowStateCleaner.clear_stale_scheduling(memory, fresh, session_id)
        if cleared:
            await self.memory.delete_keys(state.session_id, cleared)
            trace("ACTION", session_id,
                  f"stale scheduling fields cleared + synced to Redis: {cleared}")

        try:
            results = await self.tools.search_places(query)
        except Exception as exc:
            trace("ACTION", session_id, f"geo search ERROR: {exc}")
            state.response = "Place search is temporarily unavailable. Please try again."
            return state

        if isinstance(results, dict):
            results = results.get("results", [])
        if not results:
            trace("ACTION", session_id, "no places found")
            state.response = f"No nearby {query} found."
            memory["step"] = "idle"
            return state

        top = results[:5]
        place_results = [
            {"id": p.get("id"), "name": p.get("name"), "address": p.get("address")}
            for p in top
        ]
        memory["place_results"] = place_results
        memory["step"] = "selecting_place"

        # Checkpoint so the list survives until the user picks one.
        await self.memory.update(
            state.session_id,
            {"place_results": place_results, "step": "selecting_place"},
        )
        trace("ACTION", session_id,
              f"geo results stored: {len(place_results)} place(s) | step=selecting_place")

        formatted = [
            f"{i}. {p['name']} - {p['address']}"
            for i, p in enumerate(place_results, start=1)
        ]
        found_places = self.responses.get(language, "found_places")
        select_prompt = self.responses.get(language, "select_from_results")
        state.response = (
            f"{found_places} {query}:\n\n"
            + "\n".join(formatted)
            + f"\n\n{select_prompt}"
        )
        return state

    # =========================================================================
    # SELECTING PLACE (from geo search result list)
    # =========================================================================

    async def _selecting_place(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        place_results = memory.get("place_results", [])

        # LLM may classify "2" as select_doctor OR select_appointment
        # depending on context — accept either.
        selected_index = (
            memory.get("selected_doctor_index")
            or memory.get("selected_appointment_index")
        )

        trace("ACTION", session_id,
              f"selecting_place | index={selected_index} | "
              f"{len(place_results)} available")

        if not selected_index:
            # User said "yes" or something non-numeric — ask them to pick.
            state.response = BookingResponses.get(language, "doctor_prompt")
            return state

        position = selected_index - 1
        if not place_results or position < 0 or position >= len(place_results):
            state.response = BookingResponses.get(language, "invalid_selection")
            return state

        place = place_results[position]
        memory["doctor_id"] = str(place.get("id"))
        memory["doctor_name"] = place.get("name")
        memory["intent"] = "booking"
        trace("ACTION", session_id,
              f"place selected: id={memory['doctor_id']} name={memory['doctor_name']!r}")

        # Remove geo result list from memory; clear only derived scheduling
        # cache fields.  date/time are preserved — stale values were already
        # removed by searching_places at the start of this workflow, so any
        # date/time present now are valid (user supplied them in the same
        # geo search message, e.g. "find a dentist tomorrow at 9").
        memory.pop("place_results", None)
        cleared = WorkflowStateCleaner.clear_stale_scheduling(
            memory,
            fresh_fields={"date", "time"},
            session_id=session_id,
        )
        cleared.append("place_results")
        await self.memory.delete_keys(state.session_id, cleared)
        trace("ACTION", session_id,
              f"cleared from Redis: {cleared} | "
              f"post-cleanup: date={memory.get('date')!r} time={memory.get('time')!r}")

        # Route based on what is already known.
        if not memory.get("date"):
            memory["step"] = "awaiting_date"
            trace("ACTION", session_id,
                  f"selecting_place → awaiting_date | doctor={memory['doctor_id']!r}")
            state.response = (
                BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                + "\n\n" + BookingResponses.get(language, "ask_date")
            )
        elif not memory.get("time"):
            memory["step"] = "awaiting_time"
            trace("ACTION", session_id,
                  f"selecting_place → awaiting_time (date={memory['date']!r} known) | "
                  f"doctor={memory['doctor_id']!r}")
            state.response = (
                BookingResponses.get(language, "doctor_found", name=memory["doctor_name"])
                + "\n\n" + BookingResponses.get(language, "ask_time")
            )
        else:
            memory["step"] = "ready_to_book"
            trace("ACTION", session_id,
                  f"selecting_place → ready_to_book "
                  f"(date={memory['date']!r} time={memory['time']!r} both known) | "
                  f"doctor={memory['doctor_id']!r}")
            return await self._run(state)

        return state
