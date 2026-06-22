"""
SymptomCollectionHandler — multi-turn preconsultation questionnaire.

Walks the patient through 4 structured questions, then generates a
doctor-ready summary via PreconsultationSummaryService.

Steps owned:
    collecting_chief_complaint   — ask / capture chief complaint
    collecting_duration          — ask / capture how long the patient has had it
    collecting_severity          — ask / capture severity (1-10)
    collecting_associated        — ask / capture any other symptoms
    preconsultation_complete     — generate & persist summary, show recommendation

The flow is linear:
    collecting_chief_complaint
        → collecting_duration
            → collecting_severity
                → collecting_associated
                    → preconsultation_complete (show summary + specialist recommendation)
                        → [user says yes] → intent=booking → existing booking flow

State keys (all prefixed "symptom_") live in state.memory and are cleared by
WorkflowStateCleaner.clear_preconsultation_state() on cross-workflow reset.

Specialty handoff:
    _complete() stores memory["specialty"] = inferred_specialty.
    WorkflowStateCleaner.clear_preconsultation_state() does NOT clear "specialty",
    so when IntentNode forces intent=booking and WorkflowNode's cross-workflow
    reset fires, the specialty value survives and routes directly to
    searching_doctors (skipping awaiting_specialty).
"""
from __future__ import annotations

import asyncio
import re
from typing import Any

from graphs.shared.schemas import AgentState
from graphs.shared.trace import trace
from graphs.patient.services.preconsultation_service import PreconsultationSummaryService

# Steps this handler owns — used by ActionNode to route.
STEPS: frozenset[str] = frozenset({
    "collecting_chief_complaint",
    "collecting_duration",
    "collecting_severity",
    "collecting_associated",
    "preconsultation_complete",
    "awaiting_specialty_confirmation",
    "collecting_chief_complaint_booking",
    "collecting_duration_booking",
    "collecting_severity_booking",
    "collecting_associated_booking",
})

_svc = PreconsultationSummaryService()

PRECONSULT_QUESTIONS = {
    "collecting_chief_complaint": {
        "english": (
            "Before confirming your appointment, I need "
            "a few medical details to prepare your "
            "consultation. What is your main symptom "
            "or reason for visiting today?"
        ),
        "french": (
            "Avant de confirmer votre rendez-vous, j'ai "
            "besoin de quelques informations médicales. "
            "Quelle est votre plainte principale ou la "
            "raison de votre visite aujourd'hui ?"
        ),
        "arabic": (
            "قبل تأكيد موعدك، أحتاج إلى بعض التفاصيل "
            "الطبية. ما هي شكواك الرئيسية أو سبب "
            "زيارتك اليوم ؟"
        ),
    },
    "collecting_duration": {
        "english": "How long have you been experiencing this symptom?",
        "french": "Depuis combien de temps ressentez-vous ce symptôme ?",
        "arabic": "منذ متى وأنت تعاني من هذا العرض ؟",
    },
    "collecting_severity": {
        "english": (
            "On a scale from 1 to 10, how severe is your "
            "symptom? (1 = very mild, 10 = very severe)"
        ),
        "french": (
            "Sur une échelle de 1 à 10, quelle est "
            "l'intensité de votre symptôme ? "
            "(1 = très léger, 10 = très sévère)"
        ),
        "arabic": (
            "على مقياس من 1 إلى 10، ما شدة أعراضك ؟ "
            "(1 = خفيف جداً، 10 = شديد جداً)"
        ),
    },
    "collecting_associated": {
        "english": (
            "Do you have any other associated symptoms? "
            "(fever, nausea, dizziness, fatigue...) "
            "Say 'no' if there are none."
        ),
        "french": (
            "Avez-vous d'autres symptômes associés ? "
            "(fièvre, nausées, vertiges, fatigue...) "
            "Dites 'non' s'il n'y en a pas."
        ),
        "arabic": (
            "هل لديك أعراض أخرى مصاحبة ؟ "
            "(حمى، غثيان، دوار، تعب...) "
            "قل 'لا' إن لم يكن هناك أعراض أخرى."
        ),
    },
}

SPECIALTY_CONFIRM = {
    "english": (
        "Based on your symptoms, I recommend seeing "
        "a {specialty}. Would you like me to search "
        "for a {specialty}, or would you prefer a "
        "different specialty?"
    ),
    "french": (
        "D'après vos symptômes, je recommande de "
        "consulter un(e) {specialty}. Souhaitez-vous "
        "que je recherche un(e) {specialty}, ou "
        "préférez-vous une autre spécialité ?"
    ),
    "arabic": (
        "بناءً على أعراضك، أنصح باستشارة {specialty}. "
        "هل تريد أن أبحث عن {specialty}، "
        "أم تفضل تخصصاً آخر ؟"
    ),
}

SUMMARY_TEXT = {
    "english": {
        "title": "Pre-consultation summary recorded.",
        "chief": "Chief complaint",
        "duration": "Duration",
        "severity": "Severity",
        "associated": "Associated symptoms",
        "urgency": "Urgency",
        "none": "none",
        "high": "High - please consider urgent care.",
        "medium": "Moderate - please attend your appointment as scheduled.",
        "low": "Low - your condition appears non-urgent.",
    },
    "french": {
        "title": "Résumé de préconsultation enregistré.",
        "chief": "Plainte principale",
        "duration": "Durée",
        "severity": "Intensité",
        "associated": "Symptômes associés",
        "urgency": "Urgence",
        "none": "aucun",
        "high": "Élevée - veuillez envisager des soins urgents.",
        "medium": "Modérée - veuillez vous présenter au rendez-vous prévu.",
        "low": "Faible - votre état semble non urgent.",
    },
    "arabic": {
        "title": "تم تسجيل ملخص ما قبل الاستشارة.",
        "chief": "الشكوى الرئيسية",
        "duration": "المدة",
        "severity": "الشدة",
        "associated": "الأعراض المصاحبة",
        "urgency": "درجة الاستعجال",
        "none": "لا يوجد",
        "high": "مرتفعة - يرجى التفكير في رعاية عاجلة.",
        "medium": "متوسطة - يرجى الحضور إلى موعدك كما هو مقرر.",
        "low": "منخفضة - تبدو حالتك غير عاجلة.",
    },
}


def get_preconsult_question(step: str, language: str) -> str:
    lang = (language or "english").lower()
    if lang not in ("english", "french", "arabic"):
        lang = "english"
    base_step = step.replace("_booking", "")
    return PRECONSULT_QUESTIONS.get(base_step, {}).get(lang, "")

# ── Specialty inference ───────────────────────────────────────────────────────

# Keyword → specialty code. First match wins; default = médecin généraliste.
_SPECIALTY_MAP: tuple[tuple[frozenset[str], str], ...] = (
    (frozenset({
        "chest", "heart", "palpitation", "palpitations", "cardiac", "cardio",
        "blood pressure", "hypertension", "arrhythmia", "تسارع", "ألم في الصدر",
        "poitrine", "cœur", "cardiaque", "douleur thoracique",
    }), "cardiologue"),
    (frozenset({
        "skin", "rash", "itch", "itching", "acne", "eczema", "psoriasis",
        "peau", "démangeaison", "éruption",
        "جلد", "طفح", "حكة",
    }), "dermatologue"),
    (frozenset({
        "eye", "eyes", "vision", "sight", "blurry", "blur", "optic",
        "yeux", "vue", "oeil",
        "عين", "عيون", "بصر",
    }), "ophtalmologue"),
    (frozenset({
        "ear", "hearing", "throat", "nose", "sinus", "tonsil",
        "oreille", "gorge", "nez",
        "أذن", "حلق", "أنف",
    }), "ORL"),
    (frozenset({
        "bone", "joint", "knee", "hip", "spine", "back pain", "fracture",
        "articulation", "genou", "dos",
        "عظام", "مفصل", "ركبة", "ظهر",
    }), "orthopédiste"),
    (frozenset({
        "stomach", "belly", "nausea", "vomit", "diarrhea", "constipation", "abdominal",
        "ventre", "digestion", "nausée",
        "معدة", "بطن", "غثيان", "إسهال",
    }), "gastro-entérologue"),
    (frozenset({
        "headache", "migraine", "vertigo", "dizzy", "dizziness", "numbness",
        "tête", "vertige",
        "صداع", "دوخة",
    }), "neurologue"),
    (frozenset({
        "tooth", "teeth", "dental", "gum", "mouth", "toothache",
        "dent", "dentaire", "gencive",
        "سن", "أسنان", "ضرس",
    }), "dentiste"),
    (frozenset({
        "cough", "breathing", "lung", "asthma", "bronchitis", "breath",
        "toux", "poumon", "asthme", "respiration",
        "سعال", "رئة", "ربو", "تنفس",
    }), "pneumologue"),
    (frozenset({
        "urine", "kidney", "bladder", "urination", "prostate",
        "rein", "vessie",
        "كلية", "بول", "مثانة",
    }), "urologue"),
    (frozenset({
        "child", "baby", "infant", "kid",
        "enfant", "bébé", "nourrisson",
        "طفل", "رضيع",
    }), "pédiatre"),
    (frozenset({
        "thyroid", "diabetes", "hormone", "sugar",
        "thyroïde", "diabète",
        "سكري", "غدة درقية",
    }), "endocrinologue"),
    (frozenset({
        "anxiety", "depression", "mental", "stress", "panic", "mood",
        "anxiété", "dépression",
        "قلق", "اكتئاب", "نفسي",
    }), "psychiatre"),
)

# Localised display names used in the recommendation message.
_SPECIALTY_DISPLAY: dict[str, dict[str, str]] = {
    "cardiologue":         {"english": "cardiologist",       "french": "cardiologue",           "arabic": "طبيب قلب"},
    "dermatologue":        {"english": "dermatologist",      "french": "dermatologue",          "arabic": "طبيب جلدية"},
    "ophtalmologue":       {"english": "ophthalmologist",    "french": "ophtalmologue",         "arabic": "طبيب عيون"},
    "ORL":                 {"english": "ENT specialist",     "french": "ORL",                   "arabic": "طبيب أنف وأذن وحنجرة"},
    "orthopédiste":        {"english": "orthopedist",        "french": "orthopédiste",          "arabic": "طبيب عظام"},
    "gastro-entérologue":  {"english": "gastroenterologist", "french": "gastro-entérologue",    "arabic": "طبيب جهاز هضمي"},
    "neurologue":          {"english": "neurologist",        "french": "neurologue",            "arabic": "طبيب أعصاب"},
    "dentiste":            {"english": "dentist",            "french": "dentiste",              "arabic": "طبيب أسنان"},
    "pneumologue":         {"english": "pulmonologist",      "french": "pneumologue",           "arabic": "طبيب رئة"},
    "urologue":            {"english": "urologist",          "french": "urologue",              "arabic": "طبيب مسالك بولية"},
    "pédiatre":            {"english": "pediatrician",       "french": "pédiatre",              "arabic": "طبيب أطفال"},
    "endocrinologue":      {"english": "endocrinologist",    "french": "endocrinologue",        "arabic": "طبيب غدد صماء"},
    "psychiatre":          {"english": "psychiatrist",       "french": "psychiatre",            "arabic": "طبيب نفسي"},
    "médecin généraliste": {"english": "general practitioner","french": "médecin généraliste",  "arabic": "طبيب عام"},
}


def _infer_specialty(chief: str, associated: list[str]) -> str:
    """Keyword-based specialty inference. No LLM — pure deterministic matching."""
    chief_text = chief.lower()
    for keywords, specialty in _SPECIALTY_MAP:
        if any(kw in chief_text for kw in keywords):
            return specialty

    text = " ".join(associated).lower()
    for keywords, specialty in _SPECIALTY_MAP:
        if any(kw in text for kw in keywords):
            return specialty
    return "médecin généraliste"


def _recommendation_response(specialty: str, language: str) -> str:
    """Localised specialist recommendation question."""
    lang = language if language in ("english", "french", "arabic") else "english"
    name = _SPECIALTY_DISPLAY.get(specialty, {}).get(lang, specialty)
    if lang == "english":
        return (
            f"Based on the symptoms you described, I recommend consulting a **{name}**.\n\n"
            f"Would you like me to find available {name}s near you?"
        )
    if lang == "french":
        return (
            f"En fonction des symptômes décrits, je vous recommande de consulter un(e) **{name}**.\n\n"
            f"Souhaitez-vous que je recherche des {name}s disponibles près de chez vous ?"
        )
    return (
        f"بناءً على الأعراض التي وصفتها، أنصحك باستشارة **{name}**.\n\n"
        f"هل تريد أن أبحث عن {name} متاح بالقرب منك؟"
    )


def _extract_severity(text: str) -> int | None:
    """Pull the first integer 1-10 out of the user's message."""
    match = re.search(r"\b([1-9]|10)\b", text)
    return int(match.group(1)) if match else None


def _parse_associated(text: str) -> list[str]:
    """Split comma/and separated symptom list; return [] for 'no'/'none'."""
    lower = text.lower().strip()
    if lower in {"no", "none", "nothing", "non", "rien", "لا", "لا شيء"}:
        return []
    # Split on commas, semicolons, or 'and'/'et'/'و'
    parts = re.split(r"[,;]|\band\b|\bet\b|و", text, flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]

def _lang(language: str) -> str:
    lang = (language or "english").lower()
    return lang if lang in ("english", "french", "arabic") else "english"


def _specialty_display_name(specialty: str, language: str) -> str:
    lang = _lang(language)
    return _SPECIALTY_DISPLAY.get(specialty, {}).get(lang, specialty)


def _specialty_confirm_response(specialty: str, language: str) -> str:
    lang = _lang(language)
    name = _specialty_display_name(specialty, lang)
    return SPECIALTY_CONFIRM[lang].format(specialty=name)


def _preconsult_summary(
    *,
    chief: str,
    duration: str,
    severity: int,
    assoc: list[str],
    urgency: str,
    language: str,
) -> str:
    lang = _lang(language)
    labels = SUMMARY_TEXT[lang]
    assoc_text = ", ".join(assoc) if assoc else labels["none"]
    urgency_label = labels.get(urgency, labels["low"])
    return (
        f"{labels['title']}\n\n"
        f"- {labels['chief']}: {chief}\n"
        f"- {labels['duration']}: {duration}\n"
        f"- {labels['severity']}: {severity}/10\n"
        f"- {labels['associated']}: {assoc_text}\n"
        f"- {labels['urgency']}: {urgency_label}"
    )


def _is_specialty_affirmative(text: str) -> bool:
    tokens = set(re.split(r"\s+", text.lower().strip()))
    return bool(tokens & {
        "yes", "yeah", "yep", "yup", "sure", "ok", "okay", "please",
        "oui", "ouais", "d'accord", "accord", "volontiers",
        "نعم", "أجل", "حسنا", "تمام", "موافق",
        "Ù†Ø¹Ù…", "Ø£Ø¬Ù„",
    })


def _is_specialty_negative(text: str) -> bool:
    tokens = set(re.split(r"\s+", text.lower().strip()))
    return bool(tokens & {
        "no", "nope", "nah", "not", "non", "pas",
        "لا", "ليس", "غير", "Ù„Ø§",
    })


def _extract_requested_specialty(text: str) -> str | None:
    lower = text.lower().strip()
    if not lower:
        return None

    for code, names in _SPECIALTY_DISPLAY.items():
        if code.lower() in lower:
            return code
        if any(display.lower() in lower for display in names.values()):
            return code

    inferred = _infer_specialty(lower, [])
    if inferred != "mÃ©decin gÃ©nÃ©raliste":
        return inferred

    cleaned = re.sub(
        r"\b(no|non|not|instead|rather|prefer|prefere|i want|je veux|لا|أريد)\b",
        "",
        lower,
        flags=re.IGNORECASE,
    ).strip(" .؟?!،")
    return cleaned or None


class SymptomCollectionHandler:

    def __init__(self, *, redis_memory: Any) -> None:
        self.memory = redis_memory

    async def handle(self, state: AgentState) -> AgentState:
        memory = state.memory
        step = memory.get("step", "")
        session_id = state.session_id
        message = state.message.strip()

        trace("SYMPTOM", session_id, f"step={step!r} | msg={message[:60]!r}")

        if step == "collecting_chief_complaint":
            return await self._collect_complaint(state)
        if step == "collecting_duration":
            return await self._collect_duration(state)
        if step == "collecting_severity":
            return await self._collect_severity(state)
        if step == "collecting_associated":
            return await self._collect_associated(state)
        if step == "preconsultation_complete":
            return await self._complete(state)
        if step == "awaiting_specialty_confirmation":
            return await self._confirm_specialty(state)
        if step == "collecting_chief_complaint_booking":
            return await self._collect_complaint_booking(state)
        if step == "collecting_duration_booking":
            return await self._collect_duration_booking(state)
        if step == "collecting_severity_booking":
            return await self._collect_severity_booking(state)
        if step == "collecting_associated_booking":
            return await self._collect_associated_booking(state)

        language = memory.get("language", "english")
        state.response = get_preconsult_question("collecting_chief_complaint", language)
        memory["step"] = "collecting_chief_complaint"
        return state

    # ── Step 1: chief complaint ───────────────────────────────────────────────

    async def _collect_complaint(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        if not message or len(message) < 2:
            state.response = get_preconsult_question("collecting_chief_complaint", language)
            return state

        memory["symptom_chief_complaint"] = message
        memory["step"] = "collecting_duration"
        state.response = get_preconsult_question("collecting_duration", language)
        return state

    # ── Step 2: duration ─────────────────────────────────────────────────────

    async def _collect_duration(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        if not message or len(message) < 2:
            state.response = get_preconsult_question("collecting_duration", language)
            return state

        memory["symptom_duration"] = message
        memory["step"] = "collecting_severity"
        state.response = get_preconsult_question("collecting_severity", language)
        return state

    # ── Step 3: severity ─────────────────────────────────────────────────────

    async def _collect_severity(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        severity = _extract_severity(message)
        if severity is None:
            state.response = get_preconsult_question("collecting_severity", language)
            return state

        memory["symptom_severity"] = severity
        memory["step"] = "collecting_associated"
        state.response = get_preconsult_question("collecting_associated", language)
        return state

    # ── Step 4: associated symptoms ──────────────────────────────────────────

    async def _collect_associated(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()

        associated = _parse_associated(message)
        memory["symptom_associated"] = associated
        memory["step"] = "preconsultation_complete"

        # Immediately generate the summary in this same turn
        return await self._complete(state)

    # Booking flow preconsultation: doctor/date/time are already selected.

    async def _collect_complaint_booking(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        if not message or len(message) < 2:
            state.response = get_preconsult_question("collecting_chief_complaint_booking", language)
            return state

        memory["symptom_chief_complaint"] = message
        memory["step"] = "collecting_duration_booking"
        state.response = get_preconsult_question("collecting_duration_booking", language)
        return state

    async def _collect_duration_booking(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        if not message or len(message) < 2:
            state.response = get_preconsult_question("collecting_duration_booking", language)
            return state

        memory["symptom_duration"] = message
        memory["step"] = "collecting_severity_booking"
        state.response = get_preconsult_question("collecting_severity_booking", language)
        return state

    async def _collect_severity_booking(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        language = memory.get("language", "english")

        severity = _extract_severity(message)
        if severity is None:
            state.response = get_preconsult_question("collecting_severity_booking", language)
            return state

        memory["symptom_severity"] = severity
        memory["step"] = "collecting_associated_booking"
        state.response = get_preconsult_question("collecting_associated_booking", language)
        return state

    async def _collect_associated_booking(self, state: AgentState) -> AgentState:
        memory = state.memory
        message = state.message.strip()
        patient_id = state.patient_id or ""
        session_id = state.session_id

        associated = _parse_associated(message)
        memory["symptom_associated"] = associated
        chief = memory.get("symptom_chief_complaint", "")
        duration = memory.get("symptom_duration", "")
        severity = int(memory.get("symptom_severity", 5))

        await _svc.generate_and_save(
            patient_id=patient_id,
            session_id=session_id,
            chief_complaint=chief,
            duration=duration,
            severity=severity,
            associated_symptoms=associated,
            patient_profile=None,
        )
        memory["preconsultation_done"] = True
        memory["step"] = "ready_to_book"
        return state

    async def _confirm_specialty(self, state: AgentState) -> AgentState:
        memory = state.memory
        session_id = state.session_id
        message = state.message.strip()

        recommended = memory.get("recommended_specialty", "mÃ©decin gÃ©nÃ©raliste")
        requested = _extract_requested_specialty(message)

        if requested in _SPECIALTY_DISPLAY and requested != "médecin généraliste":
            # User explicitly named a recognized (non-generic) specialty — this
            # always wins, even if the message also contains an affirmative
            # word (e.g. "yes dermatologist" must not fall back to the stale
            # recommended_specialty from the preconsultation just completed).
            # "médecin généraliste" is excluded here because it is also
            # _infer_specialty's no-match default, so a plain "yes"/"ok" with
            # no real specialty mention would otherwise be misread as an
            # explicit generalist request.
            specialty = requested
        elif _is_specialty_affirmative(message) and not _is_specialty_negative(message):
            specialty = recommended
        elif requested and not _is_specialty_affirmative(message):
            specialty = requested
        else:
            specialty = recommended

        memory["specialty"] = specialty
        memory["intent"] = "booking"
        memory["step"] = "searching_doctors"
        trace("SYMPTOM", session_id,
              f"specialty confirmed | recommended={recommended!r} requested={requested!r} "
              f"selected={specialty!r}")
        return state

    # ── Step 5: generate + persist summary ───────────────────────────────────

    async def _complete(self, state: AgentState) -> AgentState:
        memory = state.memory
        patient_id = state.patient_id or ""
        session_id = state.session_id

        chief    = memory.get("symptom_chief_complaint", "")
        duration = memory.get("symptom_duration", "")
        severity = int(memory.get("symptom_severity", 5))
        assoc    = memory.get("symptom_associated", [])
        if isinstance(assoc, str):
            assoc = _parse_associated(assoc)
        language = memory.get("language", "english")

        if not chief:
            state.response = get_preconsult_question("collecting_chief_complaint", language)
            memory["step"] = "collecting_chief_complaint"
            return state

        # ── Re-entry: summary already generated this session ─────────────────
        # This branch is reached when step=preconsultation_complete, preconsultation_done=True,
        # and the user sends a new message that is NOT a booking affirmative (those are handled
        # by IntentNode's postconsult guard → intent=booking → cross-workflow reset → searching_doctors).
        #
        # Two sub-cases:
        #   A. New symptom ("I have chest pain", "my eye hurts") — user wants a NEW preconsultation.
        #      Reset preconsultation_done=False so StateWriterNode overwrites the Redis value.
        #      Forward this message to _collect_complaint() so it is captured as chief complaint
        #      this same turn (skipping the redundant "What is your symptom?" prompt).
        #
        #   B. Ambiguous/negative ("thanks", "no", "not now") — show the recommendation again.
        #
        # New-symptom heuristic: message is >= 3 words AND does not start with a negation.
        # This reliably separates descriptive symptom phrases from short affirmatives/negations.
        # (Booking affirmatives are already handled before this point by IntentNode's guard.)
        if memory.get("preconsultation_done"):
            msg_words = state.message.lower().split()
            _NEGATION_STARTERS = {"no", "non", "لا", "not", "nope", "nah", "pas"}
            is_new_complaint = (
                len(msg_words) >= 3
                and msg_words[0] not in _NEGATION_STARTERS
            )
            if is_new_complaint:
                # Reset: set False (not pop) so StateWriterNode writes False to Redis,
                # preventing MemoryNode from reloading True on the next turn.
                memory["preconsultation_done"] = False
                memory["step"] = "collecting_chief_complaint"
                trace("SYMPTOM", session_id,
                      f"new complaint after complete — resetting preconsultation | "
                      f"msg={state.message[:60]!r}")
                return await self._collect_complaint(state)

            specialty = memory.get("recommended_specialty", "médecin généraliste")
            trace("SYMPTOM", session_id,
                  f"preconsultation re-entry — showing recommendation | specialty={specialty!r}")
            state.response = _recommendation_response(specialty, language)
            return state

        # ── First time: generate and persist the summary ──────────────────────
        # Fetch patient profile for clinical context enrichment (best-effort).
        patient_profile: dict | None = None
        if patient_id:
            try:
                from app.db.mongo_client import get_database
                db = get_database()
                if db is not None:
                    patient_profile = await db["patient_profiles"].find_one(
                        {"patient_id": patient_id},
                        {"_id": 0, "gender": 1, "date_of_birth": 1, "blood_type": 1,
                         "allergies": 1, "chronic_conditions": 1, "current_medications": 1,
                         "smoking_status": 1, "alcohol_consumption": 1},
                    )
            except Exception as exc:
                trace("SYMPTOM", session_id, f"profile fetch failed (non-fatal): {exc}")

        result = await _svc.generate_and_save(
            patient_id=patient_id,
            session_id=session_id,
            chief_complaint=chief,
            duration=duration,
            severity=severity,
            associated_symptoms=assoc,
            patient_profile=patient_profile,
        )

        # Infer specialist type from symptoms.
        # Store in both keys:
        #   recommended_specialty — the inferred value (reference for re-entry fallback)
        #   specialty             — the booking pipeline key; NOT in PRECONSULTATION_FIELDS
        #                          so it survives WorkflowStateCleaner.clear_preconsultation_state()
        #                          and feeds directly into WorkflowNode's booking routing
        #                          (new_step = "searching_doctors" when specialty is set).
        specialty = _infer_specialty(chief, assoc)
        memory["recommended_specialty"] = specialty
        memory.pop("specialty", None)
        await self.memory.delete_keys(state.session_id, ["specialty"])

        trace("SYMPTOM", session_id,
              f"specialty inferred: {specialty!r} | chief={chief!r}")

        urgency_label = {
            "high":   "⚠️ High — please consider urgent care.",
            "medium": "Moderate — please attend your appointment as scheduled.",
            "low":    "Low — your condition appears non-urgent.",
        }.get(result.get("urgency", "low"), "")

        assoc_text = ", ".join(assoc) if assoc else "none"

        state.response = (
            f"Pre-consultation summary recorded.\n\n"
            f"• Chief complaint: {chief}\n"
            f"• Duration: {duration}\n"
            f"• Severity: {severity}/10\n"
            f"• Associated symptoms: {assoc_text}\n"
            f"• Urgency: {urgency_label}\n\n"
            f"{_recommendation_response(specialty, language)}"
        )

        if patient_id:
            from app.services.patient_memory_service import PatientMemoryService
            asyncio.create_task(
                PatientMemoryService().record_preconsultation(
                    patient_id=patient_id,
                    session_id=session_id,
                    chief_complaint=chief,
                    severity=severity,
                )
            )

        summary = _preconsult_summary(
            chief=chief,
            duration=duration,
            severity=severity,
            assoc=assoc,
            urgency=result.get("urgency", "low"),
            language=language,
        )
        state.response = f"{summary}\n\n{_specialty_confirm_response(specialty, language)}"
        memory["step"] = "awaiting_specialty_confirmation"
        memory["preconsultation_done"] = True
        return state
