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
from graphs.shared.normalizers.specialty_normalizer import SpecialtyNormalizer

# Steps this handler owns — used by ActionNode to route.
STEPS: frozenset[str] = frozenset({
    "searching_places",
    "selecting_place",
})

# ── Geo-service collection mapping ────────────────────────────────────────────
# Maps query keywords and place_type values to the MongoDB collection names used
# by geo_service /api/nearby.  Ordering matters: more specific entries first.

_GEO_CATEGORY: dict[str, str] = {
    "pharmacies":        "pharmacies",
    "pharmacy":          "pharmacies",
    "pharmacie":         "pharmacies",
    "صيدلية":            "pharmacies",
    "clinics":           "clinics",
    "clinic":            "clinics",
    "clinique":          "clinics",
    "hospitals":         "hospitals",
    "hospital":          "hospitals",
    "hôpital":           "hospitals",
    "hopital":           "hospitals",
    "مستشفى":            "hospitals",
    "analysis_labs":     "analysis_labs",
    "analysis_lab":      "analysis_labs",
    "laboratory":        "analysis_labs",
    "labo":              "analysis_labs",
    "nurses":            "nurses",
    "nurse":             "nurses",
    "infirmier":         "nurses",
    "physiotherapists":  "physiotherapists",
    "physiotherapist":   "physiotherapists",
    "kinésithérapeute":  "physiotherapists",
    "parapharmacies":    "parapharmacies",
    "parapharmacy":      "parapharmacies",
    "parapharmacie":     "parapharmacies",
}


def _infer_geo_category(query: str, place_type: str | None = None) -> str:
    """Return the geo_service MongoDB collection name for this query/place_type."""
    for text in (place_type or "", query or ""):
        lower = text.lower()
        for keyword, collection in _GEO_CATEGORY.items():
            if keyword in lower:
                return collection
    return "doctors"


# ── Coordinate extraction ─────────────────────────────────────────────────────
# The geo_service /api/nearby and /api/search/manual endpoints return each
# result with this structure:
#   {
#       "id": "...", "name": "...",
#       "coordinates": {"lat": 36.xxx, "lng": 10.xxx},  ← PRIMARY FORMAT
#       ...
#   }
#
# Legacy / raw formats also supported:
#   • Top-level  lat / latitude / lng / longitude / lon
#   • Google Places: geometry.location.lat / lng
#
# _extract_lat / _extract_lng try all three tiers in order so a single
# function covers every provider that may be wired in the future.

def _extract_lat(p: dict) -> float | None:
    """Extract latitude, checking all known geo_service response formats."""
    # Tier 1 — top-level scalar (OpenStreetMap, some custom providers)
    for key in ("lat", "latitude"):
        v = p.get(key)
        if v is not None:
            try:
                fv = float(v)
                if fv != 0.0:
                    return fv
            except (TypeError, ValueError):
                pass

    # Tier 2 — ClinixAI geo_service: {"coordinates": {"lat": ..., "lng": ...}}
    coords = p.get("coordinates")
    if isinstance(coords, dict):
        for key in ("lat", "latitude"):
            v = coords.get(key)
            if v is not None:
                try:
                    fv = float(v)
                    if fv != 0.0:
                        return fv
                except (TypeError, ValueError):
                    pass

    # Tier 3 — Google Places raw API: geometry.location.lat
    geo = p.get("geometry") or {}
    if isinstance(geo, dict):
        loc = geo.get("location") or {}
        if isinstance(loc, dict):
            for key in ("lat", "latitude"):
                v = loc.get(key)
                if v is not None:
                    try:
                        fv = float(v)
                        if fv != 0.0:
                            return fv
                    except (TypeError, ValueError):
                        pass

    return None


def _extract_lng(p: dict) -> float | None:
    """Extract longitude, checking all known geo_service response formats."""
    # Tier 1 — top-level scalar
    for key in ("lng", "longitude", "lon"):
        v = p.get(key)
        if v is not None:
            try:
                fv = float(v)
                if fv != 0.0:
                    return fv
            except (TypeError, ValueError):
                pass

    # Tier 2 — ClinixAI geo_service: {"coordinates": {"lat": ..., "lng": ...}}
    coords = p.get("coordinates")
    if isinstance(coords, dict):
        for key in ("lng", "longitude", "lon"):
            v = coords.get(key)
            if v is not None:
                try:
                    fv = float(v)
                    if fv != 0.0:
                        return fv
                except (TypeError, ValueError):
                    pass

    # Tier 3 — Google Places raw API: geometry.location.lng
    geo = p.get("geometry") or {}
    if isinstance(geo, dict):
        loc = geo.get("location") or {}
        if isinstance(loc, dict):
            for key in ("lng", "longitude", "lon"):
                v = loc.get(key)
                if v is not None:
                    try:
                        fv = float(v)
                        if fv != 0.0:
                            return fv
                    except (TypeError, ValueError):
                        pass

    return None


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
        place_type = memory.get("place_type")
        trace("ACTION", session_id, f"searching places | query={query!r} | place_type={place_type!r}")
        trace("ACTION", session_id,
              f"[DEBUG-SPECIALTY] geo query resolution | "
              f"memory.query={memory.get('query')!r} "
              f"memory.specialty={memory.get('specialty')!r} "
              f"memory.recommended_specialty={memory.get('recommended_specialty')!r} "
              f"-> resolved query={query!r}")

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

        # Infer which geo_service MongoDB collection to query from the natural
        # language query / place_type so results come from the right dataset.
        category = _infer_geo_category(query or "", place_type)
        trace("ACTION", session_id, f"geo_category={category!r}")

        try:
            if state.latitude is not None and state.longitude is not None:
                trace("ACTION", session_id,
                      f"nearby search | lat={state.latitude} lng={state.longitude} "
                      f"query={query!r} category={category!r}")

                payload: dict[str, Any] = {
                    "latitude":  state.latitude,
                    "longitude": state.longitude,
                    "radius":    5000,
                    "category":  category,
                }
                # For doctor searches, pass the specialty as a filter so the
                # geo_service applies a MongoDB regex match within the collection.
                if category == "doctors" and query:
                    fr_specialty = SpecialtyNormalizer.normalize(query)
                    payload["specialty"] = fr_specialty
                    if fr_specialty != query:
                        trace("ACTION", session_id,
                              f"specialty normalized: {query!r} → {fr_specialty!r}")

                results = await self.tools.search_nearby_places(payload)
            else:
                trace("ACTION", session_id, f"text search (no coords) | query={query!r}")
                # Translate specialty to French for text search too
                search_query = SpecialtyNormalizer.normalize(query) if query else query
                if search_query != query:
                    trace("ACTION", session_id,
                          f"text search specialty normalized: {query!r} → {search_query!r}")
                results = await self.tools.search_places(search_query)
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

        await self.memory.update(
            state.session_id,
            {"place_results": place_results, "step": "selecting_place"},
        )
        trace("ACTION", session_id,
              f"geo results stored: {len(place_results)} place(s) | step=selecting_place")

        # ── Build map pins with real coordinates ─────────────────────────────
        # _extract_lat / _extract_lng probe all three coordinate formats so the
        # geo_service's {"coordinates": {"lat": ..., "lng": ...}} structure is
        # handled correctly regardless of the original provider format.
        pins: list[dict] = []
        for p in top:
            lat = _extract_lat(p)
            lng = _extract_lng(p)
            pin = {
                "id":          p.get("id"),
                "name":        p.get("name"),
                "address":     p.get("address"),
                "specialty":   p.get("specialty") or query,
                "lat":         lat,
                "lng":         lng,
                "phone":       p.get("phone_number") or p.get("phone"),
                "rating":      p.get("rating"),
                "is_open_now": p.get("is_open_now"),
            }
            pins.append(pin)
            # Per-place coordinate log — visible in agent_service console.
            print(
                f"[PLACE] {p.get('name')!r:40s} | "
                f"lat={lat!r:10} lng={lng!r:10} | "
                f"addr={str(p.get('address', ''))[:40]!r}"
            )

        coords_resolved = sum(1 for p in pins if p["lat"] is not None and p["lng"] is not None)
        trace("ACTION", session_id,
              f"ui_action=open_map | {len(pins)} pin(s) | "
              f"coords_resolved={coords_resolved}/{len(pins)}")

        state.ui_action = "open_map"
        state.ui_payload = {
            "specialty":  memory.get("specialty") or query,
            "query":      query,
            "place_type": place_type,
            "pins":       pins,
        }

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

        if selected_index is None:
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
