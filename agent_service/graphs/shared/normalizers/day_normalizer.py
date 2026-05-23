from datetime import datetime
from dateparser import parse


class DayNormalizer:

    DAY_MAPPING = {

        # French
        "lundi": "lundi",
        "mardi": "mardi",
        "mercredi": "mercredi",
        "jeudi": "jeudi",
        "vendredi": "vendredi",
        "samedi": "samedi",
        "dimanche": "dimanche",

        # English
        "monday": "lundi",
        "tuesday": "mardi",
        "wednesday": "mercredi",
        "thursday": "jeudi",
        "friday": "vendredi",
        "saturday": "samedi",
        "sunday": "dimanche",

        # Arabic
        "الاثنين": "lundi",
        "الثلاثاء": "mardi",
        "الأربعاء": "mercredi",
        "الخميس": "jeudi",
        "الجمعة": "vendredi",
        "السبت": "samedi",
        "الأحد": "dimanche",
    }

    @classmethod
    def normalize(cls, value: str) -> str:

        if not value:
            raise ValueError("Day/date is required")

        value = value.strip().lower()

        # -----------------------------------
        # Direct day mapping
        # -----------------------------------

        if value in cls.DAY_MAPPING:
            return cls.DAY_MAPPING[value]

        # -----------------------------------
        # Parse any date format
        # -----------------------------------

        parsed = parse(
            value,
            languages=["fr", "en", "ar"],
        )

        if not parsed:
            raise ValueError(
                f"Cannot parse date/day: {value}"
            )

        english_day = (
            parsed
            .strftime("%A")
            .lower()
        )

        return cls.DAY_MAPPING[english_day]