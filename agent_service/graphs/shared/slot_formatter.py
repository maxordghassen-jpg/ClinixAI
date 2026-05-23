"""
Slot display formatting helper.

Converts raw slot dicts ({"start": "HH:MM", "end": "HH:MM", ...}) into
human-readable strings and supports index-based slot selection for the
awaiting_slot_selection recovery flow.

Design:
- Pure functions, no I/O, no state.
- Called from ActionNode only; never imports agent or service modules.
"""

from __future__ import annotations


class SlotFormatter:

    # ── Public API ─────────────────────────────────────────────────────────────

    @staticmethod
    def to_12h(hm: str) -> str:
        """
        Convert a 24-hour HH:MM string to a 12-hour AM/PM display string.

        "09:00" → "9:00 AM"
        "14:30" → "2:30 PM"
        "00:00" → "12:00 AM"

        Returns the original string unchanged on any parse error so callers
        never crash on unexpected input.
        """
        try:
            h, m = map(int, hm.split(":"))
            suffix = "AM" if h < 12 else "PM"
            display_h = h % 12 or 12
            return f"{display_h}:{m:02d} {suffix}"
        except Exception:
            return hm

    @staticmethod
    def numbered_list(slots: list[dict], language: str = "english") -> str:
        """
        Format a list of slot dicts as a numbered list.

        Input (time-only):   [{"start": "09:00"}, {"start": "11:30"}]
        Output:              "1. 9:00 AM\n2. 11:30 AM"

        Input (date+time):   [{"start": "09:00", "date": "2026-05-25"}, ...]
        Output:              "1. 2026-05-25 — 9:00 AM\n..."

        When a slot carries a "date" key the date is prepended so the user
        sees the full slot identity, not just the time.  Slots without "date"
        render as time-only (backward-compatible with all existing call sites).
        """
        if not slots:
            return ""
        lines = []
        for i, s in enumerate(slots, start=1):
            time_display = SlotFormatter.to_12h(s.get("start", ""))
            date = s.get("date")
            lines.append(
                f"{i}. {date} — {time_display}" if date else f"{i}. {time_display}"
            )
        return "\n".join(lines)

    @staticmethod
    def pick_by_index(suggested_slots: list[dict], index: int) -> str | None:
        """
        Return the start time of the slot at 1-based `index`.

        Returns None when index is out of range or the slot has no start.
        Used when the user says "the first one", "2", etc.
        """
        pos = index - 1
        if 0 <= pos < len(suggested_slots):
            return suggested_slots[pos].get("start") or None
        return None

    @staticmethod
    def match_typed_time(
        suggested_slots: list[dict],
        normalized_time: str,
    ) -> str | None:
        """
        Check whether `normalized_time` (HH:MM) exactly matches the start
        of one of the suggested slots.

        Returns the matched start time (canonical form from the slot), or
        None if not found.  Used as a soft-validation step so users can
        type "10:00" or "10am" and have it anchored to an actual offered slot.
        """
        for slot in suggested_slots:
            start = slot.get("start", "")
            if start == normalized_time:
                return start
        return None
