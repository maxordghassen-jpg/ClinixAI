"""
PreconsultationSummaryService — generates a doctor-ready structured narrative
from a completed symptom questionnaire.

The summary is written once when the preconsultation workflow completes
(step = preconsultation_complete) and persisted to the preconsultation_data
collection via PreconsultationRepository.upsert().

Urgency heuristic (deterministic, no LLM):
  high   → severity >= 8  OR  any red-flag keyword in chief_complaint/symptoms
  medium → severity >= 5
  low    → severity < 5

The LLM narrative uses Groq (same model as IntentNode) so that all LLM costs
run on the same provider. Prompts are in EN/FR/AR mixed — the model handles
multilingual input natively.
"""

import logging
from typing import Any

import openai

from app.config.settings import settings
from app.repositories.preconsultation_repo import PreconsultationRepository

logger = logging.getLogger(__name__)

_repo = PreconsultationRepository()

_openai = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

# Red-flag terms that escalate urgency to "high" regardless of severity score.
_RED_FLAGS = frozenset({
    # English
    "chest pain", "chest tightness", "shortness of breath", "difficulty breathing",
    "can't breathe", "cannot breathe", "heart attack", "stroke",
    "severe bleeding", "unconscious", "fainting", "seizure", "paralysis",
    "sudden vision loss", "sudden numbness",
    # French
    "douleur thoracique", "essoufflement", "difficulté à respirer",
    "ne peut pas respirer", "saignement sévère", "inconscient", "évanouissement",
    # Arabic
    "ألم في الصدر", "ضيق في التنفس", "صعوبة في التنفس", "نزيف شديد",
    "فقدان الوعي", "إغماء",
})

_SUMMARY_PROMPT = """\
You are a clinical assistant writing a concise preconsultation note for a doctor.
The patient has answered a pre-visit questionnaire. Summarise it in 3-5 sentences,
using professional medical language. Mention chief complaint, duration, severity,
associated symptoms, and any clinically relevant profile information.
Do not add diagnoses or treatments — only summarise what the patient reported.

Chief complaint : {chief_complaint}
Duration        : {duration}
Severity (1-10) : {severity}
Associated symptoms: {associated}
{profile_context}
Write only the summary paragraph. No headers. No bullet points.
"""


def _build_profile_context(profile: dict) -> str:
    """Build a compact clinical context block from a patient_profiles document."""
    lines: list[str] = []

    gender = profile.get("gender")
    dob    = profile.get("date_of_birth")
    if gender or dob:
        parts = []
        if gender:
            parts.append(f"gender={gender}")
        if dob:
            parts.append(f"DOB={dob}")
        lines.append("Demographics    : " + ", ".join(parts))

    blood_type = profile.get("blood_type")
    if blood_type:
        lines.append(f"Blood type      : {blood_type}")

    allergies = profile.get("allergies") or []
    if allergies:
        lines.append(f"Allergies       : {', '.join(allergies)}")

    conditions = profile.get("chronic_conditions") or []
    if conditions:
        lines.append(f"Chronic cond.   : {', '.join(conditions)}")

    medications = profile.get("current_medications") or []
    if medications:
        lines.append(f"Medications     : {', '.join(medications)}")

    smoking = profile.get("smoking_status")
    alcohol = profile.get("alcohol_consumption")
    if smoking or alcohol:
        lifestyle = []
        if smoking and smoking != "never":
            lifestyle.append(f"smoking={smoking}")
        if alcohol and alcohol != "never":
            lifestyle.append(f"alcohol={alcohol}")
        if lifestyle:
            lines.append("Lifestyle       : " + ", ".join(lifestyle))

    if not lines:
        return ""
    return "Patient profile :\n" + "\n".join(f"  {l}" for l in lines) + "\n"


def _compute_urgency(
    severity: int,
    chief_complaint: str,
    associated_symptoms: list[str],
) -> str:
    combined = (chief_complaint + " " + " ".join(associated_symptoms)).lower()
    for flag in _RED_FLAGS:
        if flag in combined:
            return "high"
    if severity >= 8:
        return "high"
    if severity >= 5:
        return "medium"
    return "low"


class PreconsultationSummaryService:

    async def generate_and_save(
        self,
        patient_id: str,
        session_id: str,
        chief_complaint: str,
        duration: str,
        severity: int,
        associated_symptoms: list[str],
        patient_profile: dict | None = None,
    ) -> dict[str, Any]:
        urgency = _compute_urgency(severity, chief_complaint, associated_symptoms)

        summary_text = await self._generate_summary(
            chief_complaint, duration, severity, associated_symptoms,
            patient_profile=patient_profile,
        )

        payload = {
            "chief_complaint": chief_complaint,
            "duration": duration,
            "severity": severity,
            "associated_symptoms": associated_symptoms,
            "urgency": urgency,
            "summary_text": summary_text,
        }

        await _repo.upsert(patient_id, session_id, payload)

        logger.info(
            f"[PRECONSULT SVC] summary saved | patient={patient_id} "
            f"urgency={urgency} severity={severity}"
        )
        return payload

    async def _generate_summary(
        self,
        chief_complaint: str,
        duration: str,
        severity: int,
        associated_symptoms: list[str],
        patient_profile: dict | None = None,
    ) -> str:
        associated = ", ".join(associated_symptoms) if associated_symptoms else "none reported"
        profile_context = _build_profile_context(patient_profile) if patient_profile else ""
        prompt = _SUMMARY_PROMPT.format(
            chief_complaint=chief_complaint,
            duration=duration,
            severity=severity,
            associated=associated,
            profile_context=profile_context,
        )
        try:
            resp = await _openai.chat.completions.create(
                model=settings.MODEL_NAME,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
            return text.strip()
        except Exception as exc:
            logger.error(f"[PRECONSULT SVC] LLM summary failed: {exc}")
            # Fallback: build a deterministic template summary
            assoc = associated if associated_symptoms else "no additional symptoms"
            return (
                f"Patient presents with {chief_complaint} for {duration}. "
                f"Severity rated {severity}/10. "
                f"Associated symptoms: {assoc}. "
                f"Urgency assessed as {_compute_urgency(severity, chief_complaint, associated_symptoms)}."
            )
