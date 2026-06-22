"""
Shared constants and helper functions used across all patient workflow handlers.
Extracted verbatim from action_node.py — no logic changes.
"""
from __future__ import annotations

# Words that signal agreement / affirmation — map to recovery choice 1 (try another date).
_AFFIRMATIVE_WORDS: frozenset[str] = frozenset({
    "yes", "yeah", "yep", "sure", "ok", "okay", "alright", "fine",
    "oui", "d'accord", "bien", "parfait",
    "نعم", "أجل", "تمام", "حسنا", "موافق",
})

# Keywords that signal an exploratory availability request rather than a specific
# date/time answer.  Matched against the lowercased user message word by word.
_AVAILABILITY_KEYWORDS: frozenset[str] = frozenset({
    # English
    "available", "availability", "slots", "slot", "options",
    "free", "opening", "openings", "schedule",
    # French
    "disponible", "disponibles", "disponibilité",
    "créneaux", "créneau", "horaires", "libre", "libres",
    # Arabic
    "متاح", "متاحة", "أوقات", "فراغ",
})

# Words that signal explicit negation — used in confirmation prompts to detect abort.
_NEGATIVE_WORDS: frozenset[str] = frozenset({
    "no", "nope", "nah", "never",
    "non", "jamais",
    "لا", "أبدا",
})

# Keyword groups for recovery menu choices 2/3/4.
# Ordered by priority: evaluated top-to-bottom, first match wins.
_RECOVERY_KEYWORDS: tuple[tuple[frozenset[str], int], ...] = (
    # Choice 2 — see next available
    (frozenset({"next", "available", "prochain", "suivant", "التالي", "القادم", "prochaine"}), 2),
    # Choice 4 — find nearby (check before "doctor" keywords to avoid overlap)
    (frozenset({"nearby", "near", "closest", "around", "proche", "alentour", "قريب", "مجاور", "حول"}), 4),
    # Choice 3 — choose a different doctor
    (frozenset({"different", "another", "other", "change", "new",
                "autre", "médecin", "docteur", "changer", "nouveau",
                "آخر", "طبيب", "تغيير", "جديد"}), 3),
)

# Keyword groups for the "no availability configured" recovery menu
# (choices 1/2/3 — choose another doctor / search nearby / same specialty).
# Ordered by priority: evaluated top-to-bottom, first match wins.
_AVAILABILITY_RECOVERY_KEYWORDS: tuple[tuple[frozenset[str], int], ...] = (
    # Choice 2 — search nearby doctors (check before "doctor" keywords to avoid overlap)
    (frozenset({"nearby", "near", "closest", "around", "proche", "alentour", "قريب", "مجاور", "حول"}), 2),
    # Choice 3 — search same specialty
    (frozenset({"specialty", "speciality", "specialist", "same",
                "spécialité", "même", "تخصص", "نفس"}), 3),
    # Choice 1 — choose another doctor
    (frozenset({"different", "another", "other", "change", "new", "doctor",
                "autre", "médecin", "docteur", "changer", "nouveau",
                "آخر", "طبيب", "تغيير", "جديد"}), 1),
)


def _is_availability_exploration(message: str) -> bool:
    """True when the message is asking to SEE availability rather than providing a value."""
    lowered = message.lower()
    return any(kw in lowered for kw in _AVAILABILITY_KEYWORDS)


def _format_status(status: str, language: str) -> str:
    labels = {
        "english": {"confirmed": "confirmed", "pending": "pending",
                    "cancelled": "cancelled", "rejected": "rejected"},
        "french":  {"confirmed": "confirmé", "pending": "en attente",
                    "cancelled": "annulé", "rejected": "rejeté"},
        "arabic":  {"confirmed": "مؤكد", "pending": "قيد الانتظار",
                    "cancelled": "ملغى", "rejected": "مرفوض"},
    }
    return labels.get(language, labels["english"]).get(status, status)
