"""
Reusable slot generation utilities for ClinixAI availability infrastructure.

Pure functions — no I/O, no state.
"""
from __future__ import annotations

import re

LUNCH_START = 12 * 60   # 12:00
LUNCH_END   = 14 * 60   # 14:00
_MIN_RANGE  = 15        # drop half-ranges shorter than this


def parse_hhmm(raw: str) -> int | None:
    """Parse a time string to minutes-since-midnight. Returns None on failure."""
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
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def apply_lunch_split(ranges: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """
    Insert a 12:00–14:00 lunch break into any range that spans the full midday window.

    Triggers when: open_min < 12:00 AND close_min > 13:00.
    Each half-range shorter than _MIN_RANGE minutes is dropped.
    All other ranges pass through unchanged.
    """
    result: list[tuple[int, int]] = []
    for open_min, close_min in ranges:
        if open_min < LUNCH_START and close_min > LUNCH_START + 60:
            if LUNCH_START - open_min >= _MIN_RANGE:
                result.append((open_min, LUNCH_START))
            if close_min - LUNCH_END >= _MIN_RANGE:
                result.append((LUNCH_END, close_min))
        else:
            result.append((open_min, close_min))
    return result


def generate_slots(open_min: int, close_min: int, interval: int) -> list[dict]:
    """Generate non-overlapping slot dicts for a single [open, close) range."""
    slots: list[dict] = []
    cursor = open_min
    while cursor + interval <= close_min:
        slots.append({
            "start":  minutes_to_hhmm(cursor),
            "end":    minutes_to_hhmm(cursor + interval),
            "status": "available",
        })
        cursor += interval
    return slots


def generate_slots_from_ranges(
    ranges: list[dict | tuple],
    interval: int,
) -> list[dict]:
    """
    Generate slots for a list of ranges.

    Accepts dict format {"start": "HH:MM", "end": "HH:MM"} (MongoDB storage)
    and tuple format (open_min, close_min) (internal computation).
    """
    all_slots: list[dict] = []
    for r in ranges:
        if isinstance(r, dict):
            open_min  = parse_hhmm(r.get("start", ""))
            close_min = parse_hhmm(r.get("end",   ""))
        else:
            open_min, close_min = r
        if open_min is None or close_min is None or open_min >= close_min:
            continue
        all_slots.extend(generate_slots(open_min, close_min, interval))
    return all_slots


def get_consultation_duration(document: dict, default: int = 30) -> int:
    """Extract consultation duration in minutes from an availability document."""
    raw = document.get("consultationDurationMinutes")
    try:
        return int(raw) if raw is not None else default
    except (TypeError, ValueError):
        return default
