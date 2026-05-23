"""
Scan-forward next-available-date computation.

Takes working weekdays and an async slot-fetching callback so the engine
itself remains pure (no direct HTTP calls, no service imports).

The I/O layer (AvailabilityEngine) provides the callback.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable

SCAN_DAYS = 14


async def find_next_date(
    working_weekdays: set[int],
    get_free_slots: Callable[[str], Awaitable[list[Any]]],
    start_date: date | None = None,
    scan_days: int = SCAN_DAYS,
) -> str | None:
    """
    Scan forward from start_date and return the first ISO date on which
    get_free_slots returns at least one slot.

    Args:
        working_weekdays: set of weekday ints (0=Mon … 6=Sun) to check;
                          non-working days are skipped without an HTTP call.
        get_free_slots:   async callable (iso_date: str) → list; called only
                          for working days in the scan window.
        start_date:       inclusive lower bound (exclusive: first candidate is
                          start_date + 1 day).  Defaults to today UTC.
        scan_days:        maximum calendar days to scan forward.

    Returns:
        ISO date string (YYYY-MM-DD) of the first date with free slots,
        or None if none found within the window.
    """
    if not working_weekdays:
        return None

    today = start_date or datetime.now(timezone.utc).date()

    for offset in range(1, scan_days + 1):
        candidate = today + timedelta(days=offset)
        if candidate.weekday() not in working_weekdays:
            continue
        iso = candidate.isoformat()
        slots = await get_free_slots(iso)
        if slots:
            return iso

    return None
