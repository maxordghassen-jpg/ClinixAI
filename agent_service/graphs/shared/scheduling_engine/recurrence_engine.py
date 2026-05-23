"""
French weekday ↔ integer mapping and recurring schedule utilities.

Single source of truth for all day-name logic.  No I/O, no external deps.

Replaces duplicated _FRENCH_WEEKDAY / _DAY_NAMES / _FRENCH_WEEKDAY_OFFSET
that previously lived independently in:
  - graphs/shared/services/scheduling/availability_engine.py
  - graphs/doctor/tools/availability/executor.py
  - scripts/seed_appointments.py
  - graphs/shared/normalizers/day_normalizer.py (partial overlap)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

FRENCH_DAY_TO_INT: dict[str, int] = {
    "lundi":    0,
    "mardi":    1,
    "mercredi": 2,
    "jeudi":    3,
    "vendredi": 4,
    "samedi":   5,
    "dimanche": 6,
}

INT_TO_FRENCH_DAY: dict[int, str] = {v: k for k, v in FRENCH_DAY_TO_INT.items()}

# Ordered list: index 0 = Monday (matches datetime.weekday())
DAY_NAMES: list[str] = [INT_TO_FRENCH_DAY[i] for i in range(7)]


def detect_working_weekdays(templates: list[dict[str, Any]]) -> set[int]:
    """
    Return weekday integers (0=Mon … 6=Sun) that have availability.

    A day is considered working if its template document has:
      - a non-empty 'ranges' list  (new format), OR
      - at least one non-blocked entry in 'slots'  (legacy format)
    """
    working: set[int] = set()
    for record in templates:
        if not isinstance(record, dict):
            continue
        day_name = record.get("day", "").lower()
        weekday = FRENCH_DAY_TO_INT.get(day_name)
        if weekday is None:
            continue
        if record.get("ranges"):
            working.add(weekday)
            continue
        slots = record.get("slots", [])
        if any(isinstance(s, dict) and s.get("status") != "blocked" for s in slots):
            working.add(weekday)
    return working


def current_french_day() -> str:
    """Return today's French weekday name (UTC)."""
    return INT_TO_FRENCH_DAY[datetime.now(timezone.utc).weekday()]


def resolve_day(action: str, entities: dict[str, Any]) -> str:
    """
    Resolve a French weekday name from intent action/entities context.

    Priority:
      1. entities["day"] if it is a known French day name
      2. tomorrow's weekday if the string "tomorrow" appears in action
      3. today's weekday name as fallback
    """
    if entities.get("day") and entities["day"] in FRENCH_DAY_TO_INT:
        return entities["day"]
    today = datetime.now(timezone.utc)
    if "tomorrow" in action:
        today = today + timedelta(days=1)
    return INT_TO_FRENCH_DAY[today.weekday()]
