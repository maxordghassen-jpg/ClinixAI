import re


class TimeNormalizer:

    # Matches HH:MM already
    _HM_RE = re.compile(r"^(\d{1,2}):(\d{2})$")

    # French h-format: 9h30, 14h, 9h00
    _FR_RE = re.compile(r"^(\d{1,2})h(\d{2})?$", re.IGNORECASE)

    # AM/PM: 9am, 9 am, 9:30am, 9:30 am, 9:30 AM
    _AMPM_RE = re.compile(
        r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)$", re.IGNORECASE
    )

    # Arabic PM/AM markers
    _AR_PM_RE = re.compile(r"(\d{1,2})\s*(?:مساءً|مساء)")
    _AR_AM_RE = re.compile(r"(\d{1,2})\s*(?:صباحاً|صباحا|صباح)")

    # Special words → fixed times
    _SPECIAL = {
        # English
        "noon": "12:00",
        "midnight": "00:00",
        "midday": "12:00",
        # French
        "midi": "12:00",
        "minuit": "00:00",
        # Arabic
        "الظهر": "12:00",
        "منتصف الليل": "00:00",
    }

    @classmethod
    def normalize(cls, time: str) -> str:
        """
        Returns a HH:MM string for any supported time input.
        Raises ValueError if the input cannot be parsed.
        """
        if not time:
            raise ValueError("Time is required")

        stripped = time.strip()
        lowered = stripped.lower()

        # Tier 1 — special words
        if lowered in cls._SPECIAL:
            return cls._SPECIAL[lowered]

        # Tier 2 — already HH:MM
        m = cls._HM_RE.match(stripped)
        if m:
            h, mn = int(m.group(1)), int(m.group(2))
            if 0 <= h <= 23 and 0 <= mn <= 59:
                return f"{h:02d}:{mn:02d}"

        # Tier 3 — French h-format
        m = cls._FR_RE.match(stripped)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2)) if m.group(2) else 0
            if 0 <= h <= 23 and 0 <= mn <= 59:
                return f"{h:02d}:{mn:02d}"

        # Tier 4 — AM/PM
        m = cls._AMPM_RE.match(stripped)
        if m:
            h = int(m.group(1))
            mn = int(m.group(2)) if m.group(2) else 0
            meridiem = m.group(3).lower()
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0
            if 0 <= h <= 23 and 0 <= mn <= 59:
                return f"{h:02d}:{mn:02d}"

        # Tier 5 — Arabic PM
        m = cls._AR_PM_RE.search(stripped)
        if m:
            h = int(m.group(1))
            if h != 12:
                h += 12
            if 0 <= h <= 23:
                return f"{h:02d}:00"

        # Tier 6 — Arabic AM
        m = cls._AR_AM_RE.search(stripped)
        if m:
            h = int(m.group(1))
            if h == 12:
                h = 0
            if 0 <= h <= 23:
                return f"{h:02d}:00"

        # Tier 7 — bare integer (hour only, treat as :00)
        if stripped.isdigit():
            h = int(stripped)
            if 0 <= h <= 23:
                return f"{h:02d}:00"

        raise ValueError(f"Cannot parse time: {time!r}")
