import logging
from typing import Any

from app.db.mongo_client import get_client, get_database
from app.repositories.profile_repository import MEDICAL_FIELDS, ProfileRepository
from app.schemas.medical_profile import (
    MedicalPatchRequest,
    MedicalProfile,
    PatientProfileOut,
    ProfileUpdateRequest,
)

logger = logging.getLogger(__name__)

_LIST_MEDICAL_FIELDS = [
    "allergies", "chronic_conditions", "current_medications",
    "past_surgeries", "family_history",
]


def _doc_to_out(doc: dict[str, Any]) -> PatientProfileOut:
    medical_data = {f: doc.get(f) for f in MEDICAL_FIELDS}
    for f in _LIST_MEDICAL_FIELDS:
        if medical_data[f] is None:
            medical_data[f] = []

    updated = doc.get("updated_at")

    out = PatientProfileOut(
        patient_id=doc.get("patient_id", ""),
        name=doc.get("name", ""),
        email=doc.get("email"),
        phone=doc.get("phone"),
        gender=doc.get("gender"),
        preferences=doc.get("preferences"),
        medical=MedicalProfile(**medical_data),
        recurring_symptoms=doc.get("recurring_symptoms") or [],
        preferred_specialties=doc.get("preferred_specialties") or [],
        preferred_doctors=doc.get("preferred_doctors") or [],
        updated_at=(
            updated.isoformat()
            if hasattr(updated, "isoformat")
            else str(updated) if updated else None
        ),
    )
    logger.warning(
        "[PROFILE_DEBUG] _doc_to_out | patient_id=%r | name=%r | "
        "weight=%r height=%r blood_type=%r | "
        "allergies=%d chronic=%d meds=%d | "
        "recurring_symptoms=%d preferred_specialties=%d",
        out.patient_id,
        out.name,
        out.medical.weight,
        out.medical.height,
        out.medical.blood_type,
        len(out.medical.allergies),
        len(out.medical.chronic_conditions),
        len(out.medical.current_medications),
        len(out.recurring_symptoms),
        len(out.preferred_specialties),
    )
    return out


class ProfileService:

    def __init__(self) -> None:
        self.repo = ProfileRepository()

    # ── Identity backfill ─────────────────────────────────────────────────────

    async def _backfill_identity(self, doc: dict[str, Any]) -> dict[str, Any]:
        """Fill in name/email from the users collection when missing.

        patient_profiles documents created by agent_service (via
        $setOnInsert with only patient_id/created_at) have no name or email,
        which renders as a blank "Full Name" on the profile page even though
        the canonical value lives on the linked users document.
        """
        if doc.get("name") and doc.get("email"):
            return doc

        db = get_database()
        if db is None:
            return doc

        try:
            user = await db["users"].find_one(
                {"patient_profile_id": doc.get("patient_id")},
                {"_id": 0, "name": 1, "email": 1},
            )
        except Exception as exc:
            logger.error("[PROFILE SVC] _backfill_identity failed | %s", exc)
            return doc

        if not user:
            return doc

        doc = {**doc}
        if not doc.get("name"):
            doc["name"] = user.get("name", "")
        if not doc.get("email"):
            doc["email"] = user.get("email")
        return doc

    # ── Identity resolution ───────────────────────────────────────────────────

    async def resolve_patient_id(
        self, jwt_patient_id: str | None, email: str | None
    ) -> str | None:
        """Return the canonical patient_id for this patient.

        UUID-based docs are canonical (created by the appointments system and
        confirmed by migrate_to_uuid_canonical.py).  When the JWT still carries
        an old slug-based ID (before the user re-logs in after migration), we
        detect this and redirect writes to the UUID doc immediately.

        Priority:
        1. JWT carries a slug ID AND an email-based UUID doc exists → return UUID.
        2. JWT ID resolves to a document directly → use it.
        3. Fall back to email lookup.
        4. Return jwt_patient_id as-is (new patient, no UUID doc yet).
        """
        logger.warning(
            "[WRITE_TRACE] resolve_patient_id ENTER | jwt_id=%r | email=%r | is_slug=%s",
            jwt_patient_id, email,
            bool(jwt_patient_id and jwt_patient_id.startswith("patient-")),
        )

        if jwt_patient_id and jwt_patient_id.startswith("patient-") and email:
            uuid_doc = await self.repo.get_by_email(email)
            logger.warning(
                "[WRITE_TRACE] resolve_patient_id slug-branch | email_lookup_found=%s | "
                "email_doc_id=%r",
                uuid_doc is not None,
                (uuid_doc or {}).get("patient_id"),
            )
            if uuid_doc and uuid_doc["patient_id"] != jwt_patient_id:
                correct_id = uuid_doc["patient_id"]
                logger.warning(
                    "[WRITE_TRACE] resolve_patient_id → UUID redirect | "
                    "jwt_id=%r → uuid_id=%r",
                    jwt_patient_id, correct_id,
                )
                return correct_id

        if jwt_patient_id:
            doc = await self.repo.get_by_patient_id(jwt_patient_id)
            if doc:
                logger.warning(
                    "[PROFILE_DEBUG] resolve_patient_id | jwt_id=%r RESOLVED directly",
                    jwt_patient_id,
                )
                return jwt_patient_id

        if email:
            doc = await self.repo.get_by_email(email)
            if doc:
                correct_id = doc["patient_id"]
                logger.warning(
                    "[PROFILE_DEBUG] resolve_patient_id | jwt_id=%r email=%r → correct_id=%r",
                    jwt_patient_id, email, correct_id,
                )
                return correct_id

        logger.warning(
            "[PROFILE_DEBUG] resolve_patient_id | no match | jwt_id=%r email=%r → fallback to jwt_id",
            jwt_patient_id, email,
        )
        return jwt_patient_id

    # ── Patient reads ─────────────────────────────────────────────────────────

    async def get_profile(self, patient_id: str) -> PatientProfileOut | None:
        logger.warning("[PROFILE_DEBUG] get_profile | patient_id=%r", patient_id)
        doc = await self.repo.get_by_patient_id(patient_id)
        if doc is None:
            logger.warning("[PROFILE_DEBUG] get_profile | patient_id=%r → NOT FOUND", patient_id)
            return None
        doc = await self._backfill_identity(doc)
        return _doc_to_out(doc)

    # ── Patient writes ────────────────────────────────────────────────────────

    async def update_profile(
        self, patient_id: str, body: ProfileUpdateRequest
    ) -> PatientProfileOut | None:
        fields: dict[str, Any] = {}
        if body.name is not None:
            fields["name"] = body.name
        if body.phone is not None:
            fields["phone"] = body.phone
        if body.gender is not None:
            fields["gender"] = body.gender
        if body.preferences is not None:
            fields["preferences"] = body.preferences
        if body.medical is not None:
            fields.update(body.medical.model_dump(exclude_none=True))

        logger.warning(
            "[PROFILE_DEBUG] update_profile | patient_id=%r | keys=%s",
            patient_id, sorted(fields.keys()),
        )
        if fields:
            ok = await self.repo.upsert_fields(patient_id, fields)
            if not ok:
                return None

        return await self.get_profile(patient_id)

    async def patch_medical(
        self, patient_id: str, body: MedicalPatchRequest
    ) -> PatientProfileOut | None:
        fields = body.model_dump(exclude_none=True)
        logger.warning(
            "[PROFILE_DEBUG] patch_medical | patient_id=%r | keys=%s",
            patient_id, sorted(fields.keys()),
        )
        if fields:
            ok = await self.repo.upsert_fields(patient_id, fields)
            if not ok:
                return None
        return await self.get_profile(patient_id)

    # ── Doctor access ─────────────────────────────────────────────────────────

    async def doctor_can_view(self, doctor_id: str, patient_id: str) -> bool:
        """Check if doctor has any confirmed appointment with this patient."""
        client = get_client()
        if not client:
            logger.warning("[PROFILE SVC] MongoDB client unavailable for auth check")
            return False
        try:
            appt_db = client["appointment_reservation"]
            count = await appt_db["reservations"].count_documents({
                "doctorId": doctor_id,
                "patientId": patient_id,
                "status": "confirmed",
            })
            logger.warning(
                "[PROFILE_DEBUG] doctor_can_view | doctor=%r patient=%r confirmed_count=%d",
                doctor_id, patient_id, count,
            )
            return count > 0
        except Exception as exc:
            logger.error("[PROFILE SVC] doctor_can_view check failed | %s", exc)
            return False

    async def get_profile_for_doctor_view(
        self, patient_id: str
    ) -> PatientProfileOut | None:
        """Fetch patient profile for doctor, resolving legacy slug-based patient_ids.

        The appointments collection may carry a slug-based patient_id
        (e.g. "patient-mehdiletaief") set at booking time.  If the direct
        lookup fails, we fall back to the users collection to find the
        email, then resolve via email.
        """
        doc = await self.repo.get_by_patient_id(patient_id)
        if doc:
            logger.warning(
                "[PROFILE_DEBUG] get_profile_for_doctor_view | patient_id=%r FOUND directly",
                patient_id,
            )
            doc = await self._backfill_identity(doc)
            return _doc_to_out(doc)

        # Fallback: look up user by patient_profile_id slug → get email → profile
        db = get_database()
        if db is None:
            return None
        try:
            user = await db["users"].find_one(
                {"patient_profile_id": patient_id}, {"email": 1}
            )
            if user:
                email = user.get("email", "")
                profile_doc = await self.repo.get_by_email(email)
                if profile_doc:
                    logger.warning(
                        "[PROFILE_DEBUG] get_profile_for_doctor_view | slug_id=%r email=%r → patient_id=%r",
                        patient_id, email, profile_doc.get("patient_id"),
                    )
                    profile_doc = await self._backfill_identity(profile_doc)
                    return _doc_to_out(profile_doc)
        except Exception as exc:
            logger.error(
                "[PROFILE_DEBUG] get_profile_for_doctor_view fallback failed | %s", exc
            )

        logger.warning(
            "[PROFILE_DEBUG] get_profile_for_doctor_view | patient_id=%r NOT FOUND",
            patient_id,
        )
        return None
