"""
Canonical slot generation for ClinixAI scheduling.

Single source of truth for all slot timing arithmetic.  No I/O, no imports
from app config or external services — pure Python only.

Used by:
  AvailabilityEngine (graphs.shared.services.scheduling)
  seed_appointments.py  (via sys.path agent_service injection)
  seed_availability.py  (via sys.path agent_service injection)
"""
from __future__ import annotations

import re
from typing import Any

DEFAULT_DURATION = 30  # minutes, used when template has no consultationDurationMinutes

LUNCH_START = 12 * 60   # 720  — noon in minutes
LUNCH_END   = 14 * 60   # 840  — 2 pm in minutes
MIN_RANGE   = 15        # minimum range width to keep after lunch split


# ── Primitive arithmetic ───────────────────────────────────────────────────────

def parse_hhmm(raw: str) -> int | None:
    """
    Parse a time string to minutes-since-midnight.

    Handles:
      "08:30"  "08h30"  "8:30"    (colon / h-separator)
      "0830"   "830"               (compact 4/3-digit form used by Google Maps)

    Returns None on any parse failure.
    """
    s = re.sub(r"[hH]", ":", raw.strip())
    s = re.sub(r"\s", "", s)

    m = re.match(r"^(\d{1,2}):(\d{2})$", s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h * 60 + mn
        return None

    m = re.match(r"^(\d{1,2})(\d{2})$", s)
    if m:
        h, mn = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mn <= 59:
            return h * 60 + mn

    return None


def minutes_to_hhmm(minutes: int) -> str:
    """Convert total minutes-since-midnight to 'HH:MM' string."""
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def end_time(start: str, duration_minutes: int) -> str:
    """Return the slot end time given a start HH:MM string and duration in minutes."""
    m = parse_hhmm(start)
    if m is None:
        return start
    return minutes_to_hhmm(m + duration_minutes)


# ── Lunch-split utility ────────────────────────────────────────────────────────

def apply_lunch_split(
    ranges: list[tuple[int, int]],
    lunch_start: int = LUNCH_START,
    lunch_end: int = LUNCH_END,
    min_range: int = MIN_RANGE,
) -> list[tuple[int, int]]:
    """
    Insert a lunch break into any range that spans the full midday window.

    Triggers when: open_min < lunch_start AND close_min > lunch_start + 60.
    Each resulting half-range shorter than min_range minutes is dropped.
    All other ranges pass through unchanged.
    """
    result: list[tuple[int, int]] = []
    for open_min, close_min in ranges:
        if open_min < lunch_start and close_min > lunch_start + 60:
            if lunch_start - open_min >= min_range:
                result.append((open_min, lunch_start))
            if close_min - lunch_end >= min_range:
                result.append((lunch_end, close_min))
        else:
            result.append((open_min, close_min))
    return result


# ── Slot generation — start-time strings ──────────────────────────────────────

def generate_slots_from_ranges(
    ranges: list[dict[str, Any]],
    duration_minutes: int,
) -> list[str]:
    """
    Generate HH:MM start-time strings from a list of range dicts.

    Each range dict must have "start" and "end" keys in any format parse_hhmm
    can handle.  Slots are generated at `duration_minutes` intervals; no slot
    is generated if it would end past the range boundary.

    Returns an ordered list of HH:MM start strings.
    """
    starts: list[str] = []
    for r in ranges:
        start_min = parse_hhmm(r.get("start", ""))
        end_min   = parse_hhmm(r.get("end", ""))
        if start_min is None or end_min is None:
            continue
        cursor = start_min
        while cursor + duration_minutes <= end_min:
            starts.append(minutes_to_hhmm(cursor))
            cursor += duration_minutes
    return starts


def generate_slots_from_legacy(slots: list[dict[str, Any]]) -> list[str]:
    """
    Extract non-blocked slot start-time strings from a legacy slots array.

    A slot is included if it is not blocked and has a non-empty "start" key.
    """
    return [
        s["start"]
        for s in slots
        if isinstance(s, dict)
        and s.get("status") != "blocked"
        and s.get("start")
    ]


def generate_slots(
    template: dict[str, Any],
    duration_minutes: int | None = None,
) -> list[str]:
    """
    Generate slot start-time strings from a weekly template document.

    Prefers the 'ranges' format (new); falls back to 'slots' array (legacy).
    Uses template's 'consultationDurationMinutes' when duration_minutes is None.
    """
    if not template:
        return []
    duration = duration_minutes or template.get("consultationDurationMinutes", DEFAULT_DURATION)
    ranges = template.get("ranges")
    if ranges:
        return generate_slots_from_ranges(ranges, duration)
    return generate_slots_from_legacy(template.get("slots", []))


# ── Slot generation — full slot dicts (for template seeding) ──────────────────

def generate_slot_dicts(
    open_min: int,
    close_min: int,
    duration_minutes: int,
) -> list[dict[str, str]]:
    """
    Generate slot dicts {start, end, status: "available"} for one time range.

    All slots are exactly `duration_minutes` long.  The last slot's end equals
    close_min (no partial slots are emitted).
    """
    slots: list[dict[str, str]] = []
    cursor = open_min
    while cursor + duration_minutes <= close_min:
        slots.append({
            "start":  minutes_to_hhmm(cursor),
            "end":    minutes_to_hhmm(cursor + duration_minutes),
            "status": "available",
        })
        cursor += duration_minutes
    return slots


def generate_slot_dicts_from_ranges(
    ranges: list[tuple[int, int]],
    duration_minutes: int,
) -> list[dict[str, str]]:
    """
    Generate slot dicts for a list of (open_min, close_min) tuples.

    Used by seed_availability.py to build weekly template documents.
    """
    all_slots: list[dict[str, str]] = []
    for open_min, close_min in ranges:
        all_slots.extend(generate_slot_dicts(open_min, close_min, duration_minutes))
    return all_slots
