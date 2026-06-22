import re
from datetime import datetime, timedelta

import dateparser


class DateNormalizer:

    # Relative keywords → day offset, keyed by lowercase stripped value
    _RELATIVE = {
        # English
        "today": 0,
        "tomorrow": 1,
        "yesterday": -1,
        "the day after tomorrow": 2,
        "after tomorrow": 2,
        # French
        "aujourd'hui": 0,
        "demain": 1,
        "hier": -1,
        "après-demain": 2,
        "apres-demain": 2,
        # Arabic
        "اليوم": 0,
        "غداً": 1,
        "غدا": 1,
        "أمس": -1,
        "بعد غد": 2,
        "بعد غداً": 2,
        # Weeks
        "next week": 7,
        "semaine prochaine": 7,
        "الأسبوع القادم": 7,
    }

    # Matches YYYY-MM-DD (already ISO)
    _ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    # Matches DD/MM/YYYY or DD-MM-YYYY
    _EU_RE = re.compile(r"^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$")

    @classmethod
    def normalize(cls, date: str) -> str:
        """
        Returns a YYYY-MM-DD string for any supported date input.
        Raises ValueError if the input cannot be parsed.
        """
        if not date:
            raise ValueError("Date is required")

        stripped = date.strip()
        lowered = stripped.lower()

        # Tier 1 — hardcoded relative keywords
        if lowered in cls._RELATIVE:
            delta = cls._RELATIVE[lowered]
            return (datetime.now() + timedelta(days=delta)).strftime("%Y-%m-%d")

        # Tier 2 — already ISO
        if cls._ISO_RE.match(stripped):
            return stripped

        # Tier 3 — European DD/MM/YYYY
        eu_match = cls._EU_RE.match(stripped)
        if eu_match:
            day, month, year = eu_match.groups()
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"

        # Clean up 'next'/'prochain' before feeding to dateparser, which struggles with it.
        # PREFER_DATES_FROM="future" will automatically push the date to next week.
        for prefix in ["next ", "prochain "]:
            if stripped.lower().startswith(prefix):
                stripped = stripped[len(prefix):]
        for suffix in [" prochain", " next"]:
            if stripped.lower().endswith(suffix):
                stripped = stripped[:-len(suffix)]

        # Tier 4 — dateparser (handles day names, relative phrases, multilingual)
        parsed = dateparser.parse(
            stripped,
            languages=["en", "fr", "ar"],
            settings={"PREFER_DATES_FROM": "future"},
        )
        if parsed:
            return parsed.strftime("%Y-%m-%d")

        raise ValueError(f"Cannot parse date: {date!r}")

    @classmethod
    def normalize_safe(cls, date: str | None) -> str | None:
        """Return YYYY-MM-DD or None on any failure.  Never raises."""
        if not date:
            return None
        try:
            return cls.normalize(date)
        except ValueError:
            return None
