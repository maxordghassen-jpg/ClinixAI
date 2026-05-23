"""
Combine template + exception + existing bookings → free slot times.

Pure computation — no I/O.  Takes already-fetched data structures so the
caller (AvailabilityEngine, seed scripts, etc.) handles all data retrieval.
"""
from __future__ import annotations

from typing import Any

from .slot_generator import generate_slots, generate_slots_from_ranges, DEFAULT_DURATION
from .exception_resolver import is_day_blocked, get_override_ranges
from .conflict_detector import filter_free


def resolve_available_slots(
    template: dict[str, Any] | None,
    exception: dict[str, Any] | None,
    booked_times: set[str] | None = None,
    override_duration: int = DEFAULT_DURATION,
) -> list[str]:
    """
    Compute free slot start-time strings for a single calendar day.

    Resolution order:
      1. exception is a closure/vacation  → [] (day is fully blocked)
      2. exception is an override          → generate from overrideRanges
      3. template exists                   → generate from template ranges/slots
      4. no template and no exception      → []

    Then booked_times are filtered out.

    Args:
        template:         weekly template document for the day, or None
        exception:        exception document for the date, or None
        booked_times:     set of already-booked HH:MM strings to exclude
        override_duration: slot duration (minutes) used for override ranges

    Returns:
        Ordered list of free HH:MM start-time strings.
    """
    if exception is not None:
        if is_day_blocked(exception):
            return []
        override_ranges = get_override_ranges(exception)
        if override_ranges:
            all_times = generate_slots_from_ranges(override_ranges, override_duration)
        else:
            return []
    elif template is not None:
        all_times = generate_slots(template)
    else:
        return []

    if not booked_times:
        return all_times

    return filter_free(all_times, booked_times)
