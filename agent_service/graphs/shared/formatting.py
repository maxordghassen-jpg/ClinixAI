from datetime import datetime
from typing import Any


MONTHS = {
    "en": [
        "January",
        "February",
        "March",
        "April",
        "May",
        "June",
        "July",
        "August",
        "September",
        "October",
        "November",
        "December",
    ],
    "fr": [
        "janvier",
        "février",
        "mars",
        "avril",
        "mai",
        "juin",
        "juillet",
        "août",
        "septembre",
        "octobre",
        "novembre",
        "décembre",
    ],
    "ar": [
        "يناير",
        "فبراير",
        "مارس",
        "أبريل",
        "مايو",
        "يونيو",
        "يوليو",
        "أغسطس",
        "سبتمبر",
        "أكتوبر",
        "نوفمبر",
        "ديسمبر",
    ],
}

WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "fr": ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"],
    "ar": ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"],
}


STATUS_LABELS = {
    "en": {
        "confirmed": "confirmed",
        "pending": "pending",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "canceled": "cancelled",
        "available": "available",
        "blocked": "blocked",
        "booked": "booked",
    },
    "fr": {
        "confirmed": "confirmé",
        "pending": "en attente",
        "rejected": "refusé",
        "cancelled": "annulé",
        "canceled": "annulé",
        "available": "disponible",
        "blocked": "bloqué",
        "booked": "réservé",
    },
    "ar": {
        "confirmed": "مؤكد",
        "pending": "قيد الانتظار",
        "rejected": "مرفوض",
        "cancelled": "ملغى",
        "canceled": "ملغى",
        "available": "متاح",
        "blocked": "محجوب",
        "booked": "محجوز",
    },
}


def normalize_language(language: str | None) -> str:
    if not language:
        return "en"

    value = language.lower()
    if value.startswith("fr") or "french" in value or "français" in value:
        return "fr"
    if value.startswith("ar") or "arabic" in value or "عربي" in value:
        return "ar"
    return "en"


def parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def format_date(value: Any, language: str) -> str | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None

    month = MONTHS[language][parsed.month - 1]
    if language == "fr":
        return f"{parsed.day} {month}"
    if language == "ar":
        return f"{parsed.day} {month}"
    return f"{month} {parsed.day}"


def format_weekday(value: Any, language: str) -> str | None:
    parsed = parse_datetime(value)
    if not parsed:
        return None
    return WEEKDAYS[language][parsed.weekday()]


def format_status(status: str | None, language: str) -> str:
    if not status:
        return STATUS_LABELS[language].get("pending", "pending")
    return STATUS_LABELS[language].get(status.lower(), status)


def patient_display_name(item: dict[str, Any]) -> str:
    name = (
        item.get("patient_name")
        or item.get("patientName")
        or item.get("patient")
        or item.get("name")
    )
    if name:
        return str(name)

    patient_id = item.get("patient_id") or item.get("patientId")
    if patient_id:
        return f"Patient #{patient_id}"
    return "Patient"


def doctor_display_name(item: dict[str, Any]) -> str:
    name = (
        item.get("doctor_name")
        or item.get("doctorName")
        or item.get("doctor")
        or item.get("name")
    )
    if name:
        value = str(name)
        return value if value.lower().startswith("dr") else f"Dr. {value}"

    doctor_id = item.get("doctor_id") or item.get("doctorId")
    if doctor_id:
        return f"Dr. #{doctor_id}"
    return "Doctor"


def appointment_date_context(items: list[dict[str, Any]], action: str | None, language: str) -> str | None:
    if action == "view_today_appointments":
        return {"en": "today", "fr": "aujourd’hui", "ar": "اليوم"}[language]
    if action == "view_tomorrow_appointments":
        return {"en": "tomorrow", "fr": "demain", "ar": "غدًا"}[language]
    if action == "view_week_appointments":
        return {"en": "this week", "fr": "cette semaine", "ar": "هذا الأسبوع"}[language]
    if action == "view_next_week_appointments":
        return {"en": "next week", "fr": "la semaine prochaine", "ar": "الأسبوع القادم"}[language]

    dates = {item.get("date") for item in items if item.get("date")}
    if len(dates) == 1:
        return format_date(next(iter(dates)), language)
    return None


def appointment_header(count: int, context: str | None, language: str) -> str:
    if language == "fr":
        base = f"Vous avez {count} rendez-vous"
        return f"{base} {context} :" if context else f"{base} :"
    if language == "ar":
        if count == 1:
            base = "لديك موعد واحد"
        elif count == 2:
            base = "لديك موعدان"
        else:
            base = f"لديك {count} مواعيد"
        return f"{base} {context}:" if context else f"{base}:"

    base = f"You have {count} appointment" if count == 1 else f"You have {count} appointments"
    return f"{base} on {context}:" if context and context not in {"today", "tomorrow", "this week", "next week"} else (
        f"{base} {context}:" if context else f"{base}:"
    )


def empty_message(language: str) -> str:
    return {
        "en": "No matching results were found.",
        "fr": "Aucun résultat correspondant n’a été trouvé.",
        "ar": "لم يتم العثور على نتائج مطابقة.",
    }[language]


def completed_message(language: str) -> str:
    return {
        "en": "The request was completed.",
        "fr": "La demande a été effectuée.",
        "ar": "تم تنفيذ الطلب.",
    }[language]


def format_daily_schedule(
    items: list[dict[str, Any]],
    language: str,
    context: str | None = None,
) -> str:
    """
    Compact calendar view for the doctor’s schedule.

    Each line: "10:00 — Ahmed Ben Ali (confirmed)"
    Groups multiple dates with a date header when the list spans more than one day.

    Returns an empty_message if the list is empty.
    """
    if not items:
        return empty_message(language)

    header_templates = {
        "en": "Schedule{ctx}:",
        "fr": "Planning{ctx} :",
        "ar": "جدول{ctx}:",
    }
    ctx_str = f" — {context}" if context else ""
    header = header_templates.get(language, header_templates["en"]).format(ctx=ctx_str)

    # Detect multi-day: group by date
    from collections import defaultdict
    by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in sorted(items, key=lambda a: (str(a.get("date", "")), a.get("time", ""))):
        date_key = _date_key(item.get("date"))
        by_date[date_key].append(item)

    lines = [header]
    multi_day = len(by_date) > 1

    for date_key, day_items in sorted(by_date.items()):
        if multi_day:
            date_label = format_date(date_key, language) or date_key
            lines.append(f"\n📅 {date_label}")

        for item in day_items:
            time_val  = item.get("time", "--:--")
            end_time  = item.get("end_time")
            name      = patient_display_name(item)
            raw_status = item.get("status", "pending")
            status_lbl = format_status(raw_status, language)

            time_range = f"{time_val}–{end_time}" if end_time else time_val
            lines.append(f"  {time_range}  —  {name}  ({status_lbl})")

    return "\n".join(lines)


def _date_key(value: Any) -> str:
    """Extract a YYYY-MM-DD string from a date field (datetime or string)."""
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
        except ValueError:
            return value
    return str(value)
