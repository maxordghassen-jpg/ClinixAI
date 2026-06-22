"""
Availability check workflow handler.

Handles check_availability intent: resolve a doctor by name, fetch their
free slots on a given date, present them, and optionally transition into
the booking flow when the patient selects a slot.

Steps owned:
    checking_availability_doctor  — transient: resolve doctor + fetch slots
    awaiting_availability_date    — persistent: waiting for patient to supply date
"""
from __future__ import annotations

import logging
from datetime import datetime as _dt, date as _date_cls
from typing import Any

from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.shared.slot_formatter import SlotFormatter
from graphs.shared.normalizers.date_normalizer import DateNormalizer

logger = logging.getLogger(__name__)

STEPS: frozenset[str] = frozenset({
    "checking_availability_doctor",
    "awaiting_availability_date",
})

# ── Localised response strings ────────────────────────────────────────────────

_RESPONSES: dict[str, dict[str, str]] = {
    "english": {
        "slots_found":        (
            "Dr. {name} has available appointments on {date}:\n\n"
            "{slots}\n\n"
            "Would you like me to reserve one of these slots?"
        ),
        "no_slots":           (
            "Dr. {name} has no available appointments on {date}. "
            "Would you like to check a different date, or book with another doctor?"
        ),
        "doctor_not_found":   (
            "I couldn't find a doctor named '{name}' in our system. "
            "Please check the spelling or search by specialty instead."
        ),
        "ask_date":           "What date would you like to check for {name}?",
        "ask_doctor":         "Which doctor would you like to check availability for?",
        "lookup_error":       (
            "I couldn't retrieve the schedule right now. "
            "Please try again in a moment."
        ),
        "invalid_date":       (
            "I couldn't understand that date. "
            "Please try again (e.g. 'tomorrow', 'Friday', '15 June')."
        ),
    },
    "french": {
        "slots_found":        (
            "Le Dr. {name} est disponible le {date} :\n\n"
            "{slots}\n\n"
            "Voulez-vous que je réserve l'un de ces créneaux ?"
        ),
        "no_slots":           (
            "Le Dr. {name} n'a pas de créneaux disponibles le {date}. "
            "Voulez-vous essayer une autre date ou choisir un autre médecin ?"
        ),
        "doctor_not_found":   (
            "Je n'ai pas trouvé de médecin nommé '{name}' dans notre système. "
            "Vérifiez l'orthographe ou cherchez par spécialité."
        ),
        "ask_date":           "Quelle date souhaitez-vous vérifier pour {name} ?",
        "ask_doctor":         "Pour quel médecin souhaitez-vous vérifier la disponibilité ?",
        "lookup_error":       (
            "Impossible de récupérer le planning pour l'instant. "
            "Veuillez réessayer."
        ),
        "invalid_date":       (
            "Je n'ai pas compris cette date. "
            "Essayez de nouveau (ex. 'demain', 'vendredi', '15 juin')."
        ),
    },
    "arabic": {
        "slots_found":        (
            "الدكتور {name} متاح في تاريخ {date}:\n\n"
            "{slots}\n\n"
            "هل تريدني أن أحجز لك أحد هذه المواعيد؟"
        ),
        "no_slots":           (
            "الدكتور {name} لا يملك مواعيد متاحة في تاريخ {date}. "
            "هل تريد تجربة تاريخ آخر أو اختيار طبيب آخر؟"
        ),
        "doctor_not_found":   (
            "لم أجد طبيباً باسم '{name}' في النظام. "
            "تحقق من الإملاء أو ابحث بالتخصص."
        ),
        "ask_date":           "ما التاريخ الذي تريد التحقق منه لـ {name}؟",
        "ask_doctor":         "أي طبيب تريد التحقق من مواعيده المتاحة؟",
        "lookup_error":       "تعذّر الحصول على الجدول حالياً. يرجى المحاولة مرة أخرى.",
        "invalid_date":       "لم أفهم هذا التاريخ. حاول مجدداً (مثال: 'غداً'، 'الجمعة'، '15 يونيو').",
    },
}


def _t(language: str, key: str, **kwargs) -> str:
    lang = (language or "english").lower()
    table = _RESPONSES.get(lang, _RESPONSES["english"])
    tpl = table.get(key, _RESPONSES["english"].get(key, key))
    return tpl.format(**kwargs) if kwargs else tpl


def _display_date(iso_date: str) -> str:
    """Format YYYY-MM-DD as a human-readable string ('today', 'tomorrow', 'Thursday, May 29')."""
    try:
        d = _dt.strptime(iso_date, "%Y-%m-%d").date()
        today = _date_cls.today()
        diff = (d - today).days
        if diff == 0:
            return "today"
        if diff == 1:
            return "tomorrow"
        if 2 <= diff <= 6:
            return d.strftime("%A")
        return d.strftime("%A, %B %d").replace(" 0", " ")
    except Exception:
        return iso_date


class AvailabilityCheckHandler:
    """Looks up a specific doctor's free slots on a requested date."""

    def __init__(
        self,
        *,
        availability_service: Any,
        doctor_service: Any,
        redis_memory: Any,
    ) -> None:
        self.availability_service = availability_service
        self.doctor_service = doctor_service
        self.memory = redis_memory

    async def handle(self, state: AgentState) -> AgentState:
        step = state.memory.get("step")
        if step in STEPS:
            return await self._check_availability(state)
        return state

    async def _check_availability(self, state: AgentState) -> AgentState:
        try:
            return await self._check_availability_inner(state)
        except Exception:
            session_id = getattr(state, "session_id", "unknown")
            logger.exception(
                "AVAIL_CHECK unhandled error | session=%s", session_id
            )
            trace("ACTION", session_id, "check_availability — unhandled exception (see logs)")
            language = state.memory.get("language", "english") if state.memory else "english"
            state.response = _t(language, "lookup_error")
            return state

    async def _check_availability_inner(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        language = memory.get("language", "english")

        doctor_name = memory.get("doctor_name")
        doctor_id   = memory.get("doctor_id")
        date_raw    = memory.get("date")

        trace("ACTION", session_id,
              f"check_availability | doctor_name={doctor_name!r} "
              f"doctor_id={doctor_id!r} date={date_raw!r}")
        logger.debug(
            "AVAIL_CHECK start | session=%s doctor_name=%r doctor_id=%r date=%r",
            session_id, doctor_name, doctor_id, date_raw,
        )

        # ── Guard: need at least a doctor reference ────────────────────────
        if not doctor_name and not doctor_id:
            memory["step"] = "awaiting_availability_date"
            state.response = _t(language, "ask_doctor")
            logger.debug("AVAIL_CHECK guard: no doctor reference → ask_doctor")
            return state

        display_name = doctor_name or "this doctor"

        # ── Guard: need a date ─────────────────────────────────────────────
        if not date_raw:
            memory["step"] = "awaiting_availability_date"
            state.response = _t(language, "ask_date", name=display_name)
            logger.debug("AVAIL_CHECK guard: no date → ask_date for %r", display_name)
            return state

        # ── Resolve doctor name → doctor_id ───────────────────────────────
        resolved_name = doctor_name or ""

        if not doctor_id and doctor_name:
            try:
                results = await self.doctor_service.search(doctor_name)
                logger.debug(
                    "AVAIL_CHECK doctor search | query=%r results_count=%d",
                    doctor_name, len(results) if results else 0,
                )
                if results:
                    doc = results[0]
                    doctor_id    = str(doc.get("id") or "")
                    resolved_name = doc.get("name") or doctor_name
                    memory["doctor_id"]   = doctor_id
                    memory["doctor_name"] = resolved_name
                    trace("ACTION", session_id,
                          f"doctor resolved: {doctor_name!r} → "
                          f"id={doctor_id!r} name={resolved_name!r}")
                    logger.debug(
                        "AVAIL_CHECK doctor resolved: %r → id=%r name=%r",
                        doctor_name, doctor_id, resolved_name,
                    )
                else:
                    trace("ACTION", session_id,
                          f"no doctors found for name={doctor_name!r}")
                    logger.debug("AVAIL_CHECK doctor not found: %r", doctor_name)
            except Exception as exc:
                trace("ACTION", session_id, f"doctor lookup ERROR: {exc!r}")
                logger.exception(
                    "AVAIL_CHECK doctor lookup error | session=%s name=%r",
                    session_id, doctor_name,
                )

        if not doctor_id:
            memory["step"] = "idle"
            state.response = _t(language, "doctor_not_found", name=doctor_name or "")
            await self.memory.update(state.session_id, {"step": "idle"})
            logger.debug("AVAIL_CHECK doctor_not_found → idle | name=%r", doctor_name)
            return state

        # ── Normalize date ─────────────────────────────────────────────────
        try:
            iso_date = DateNormalizer.normalize(date_raw)
            logger.debug("AVAIL_CHECK date normalized: %r → %r", date_raw, iso_date)
        except Exception as exc:
            trace("ACTION", session_id, f"date normalization ERROR: {exc!r} | date_raw={date_raw!r}")
            logger.warning(
                "AVAIL_CHECK date normalization failed | session=%s date_raw=%r exc=%r",
                session_id, date_raw, exc,
            )
            memory.pop("date", None)
            await self.memory.delete_keys(state.session_id, ["date"])
            memory["step"] = "awaiting_availability_date"
            state.response = _t(language, "invalid_date")
            return state

        # ── Fetch free slots ───────────────────────────────────────────────
        try:
            slots = await self.availability_service.get_free_slots(
                doctor_id=doctor_id, date=iso_date,
            )
            logger.debug(
                "AVAIL_CHECK slot fetch | doctor_id=%r date=%r raw_count=%d",
                doctor_id, iso_date, len(slots) if slots else 0,
            )
        except Exception as exc:
            trace("ACTION", session_id, f"availability fetch ERROR: {exc!r}")
            logger.exception(
                "AVAIL_CHECK slot fetch error | session=%s doctor_id=%r date=%r",
                session_id, doctor_id, iso_date,
            )
            state.response = _t(language, "lookup_error")
            return state

        valid_slots = [s for s in (slots or []) if isinstance(s, dict) and s.get("start")]
        date_display = _display_date(iso_date)

        trace("ACTION", session_id,
              f"slots found: {len(valid_slots)} | "
              f"doctor={resolved_name!r} date={iso_date!r}")
        logger.debug(
            "AVAIL_CHECK result | valid_slots=%d doctor=%r date=%r",
            len(valid_slots), resolved_name, iso_date,
        )

        if valid_slots:
            slots_text = SlotFormatter.numbered_list(valid_slots, language)
            state.response = _t(
                language, "slots_found",
                name=resolved_name,
                date=date_display,
                slots=slots_text,
            )
            # Transition into booking slot-selection so patient can confirm
            memory["date"]            = iso_date
            memory["suggested_slots"] = valid_slots
            memory["intent"]          = "booking"
            memory["step"]            = "awaiting_slot_selection"
            await self.memory.update(
                state.session_id,
                {
                    "doctor_id":       doctor_id,
                    "doctor_name":     resolved_name,
                    "date":            iso_date,
                    "suggested_slots": valid_slots,
                    "intent":          "booking",
                    "step":            "awaiting_slot_selection",
                },
            )
        else:
            state.response = _t(
                language, "no_slots",
                name=resolved_name,
                date=date_display,
            )
            memory["step"] = "idle"
            await self.memory.update(state.session_id, {"step": "idle"})

        return state
