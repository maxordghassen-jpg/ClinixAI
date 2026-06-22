"""
PatientProfileRepository — raw Motor operations on two collections:

  patient_profiles  — one document per patient, upserted on every meaningful event
  reminder_jobs     — one document per scheduled reminder, written on booking success

Design rules:
  - All methods return None on MongoDB unavailability (get_database() returns None).
  - No method raises — callers (PatientMemoryService) handle None returns.
  - appointment_history is capped at MAX_HISTORY entries using $slice in the
    $push / $each / $slice operator. This keeps the document size bounded for
    high-frequency patients without a separate cleanup job.
  - preferred_doctors, preferred_specialties, preferred_times are deduplicated
    via $addToSet where possible, or via read-modify-write for ordered lists.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.mongo_client import get_database

logger = logging.getLogger(__name__)

MAX_HISTORY = 50          # max appointment_history entries per patient
MAX_PREFERRED = 10        # max entries in preferred_doctors / preferred_times lists


class PatientProfileRepository:

    PROFILES_COLLECTION = "patient_profiles"
    REMINDERS_COLLECTION = "reminder_jobs"

    # =========================================================================
    # PROFILE — READ
    # =========================================================================

    async def get_by_patient_id(self, patient_id: str) -> dict[str, Any] | None:
        db = get_database()
        if db is None:
            return None
        try:
            return await db[self.PROFILES_COLLECTION].find_one(
                {"patient_id": patient_id},
                {"_id": 0},
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] get_by_patient_id failed | patient={patient_id} | {exc}")
            return None

    # =========================================================================
    # PROFILE — IDENTITY RESOLUTION
    # Mirrors auth_service.ProfileService.resolve_patient_id: a patient's JWT
    # may carry a slug-based id ("patient-{slug}") issued at signup, while a
    # richer UUID-based document (created by the appointments system) already
    # exists for the same email. Without this resolution, agent_service would
    # read/write a different patient_profiles document than the one the
    # "My Profile" page resolves to via auth_service.
    # =========================================================================

    async def resolve_patient_id(
        self,
        jwt_patient_id: str | None,
        email: str | None,
    ) -> str | None:
        db = get_database()
        if db is None:
            return jwt_patient_id

        try:
            if jwt_patient_id and jwt_patient_id.startswith("patient-") and email:
                email_doc = await db[self.PROFILES_COLLECTION].find_one(
                    {"email": email.lower()}, {"_id": 0, "patient_id": 1}
                )
                if email_doc and email_doc.get("patient_id") != jwt_patient_id:
                    return email_doc["patient_id"]

            if jwt_patient_id:
                existing = await db[self.PROFILES_COLLECTION].find_one(
                    {"patient_id": jwt_patient_id}, {"_id": 0, "patient_id": 1}
                )
                if existing:
                    return jwt_patient_id

            if email:
                email_doc = await db[self.PROFILES_COLLECTION].find_one(
                    {"email": email.lower()}, {"_id": 0, "patient_id": 1}
                )
                if email_doc:
                    return email_doc["patient_id"]
        except Exception as exc:
            logger.error(f"[PROFILE REPO] resolve_patient_id failed | jwt_id={jwt_patient_id} | {exc}")

        return jwt_patient_id

    # =========================================================================
    # PROFILE — UPSERT SCALAR FIELDS
    # Used for: language, reminder_preferences, stats increments
    # =========================================================================

    async def upsert_fields(
        self,
        patient_id: str,
        fields: dict[str, Any],
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$set": {**fields, "updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] upsert_fields failed | patient={patient_id} | {exc}")

    # =========================================================================
    # PROFILE — INCREMENT STATS COUNTER
    # =========================================================================

    async def increment_stat(self, patient_id: str, field: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$inc": {f"stats.{field}": 1},
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] increment_stat failed | patient={patient_id} field={field} | {exc}")

    # =========================================================================
    # PROFILE — APPOINTMENT HISTORY
    # Pushes one entry and keeps the list capped at MAX_HISTORY (most recent).
    # MongoDB $slice with a negative number keeps the last N elements.
    # =========================================================================

    async def push_appointment_history(
        self,
        patient_id: str,
        entry: dict[str, Any],
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$push": {
                        "appointment_history": {
                            "$each": [entry],
                            "$slice": -MAX_HISTORY,
                            "$sort": {"booked_at": 1},
                        }
                    },
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] push_appointment_history failed | patient={patient_id} | {exc}")

    # =========================================================================
    # PROFILE — PREFERRED SPECIALTIES
    # Adds specialty via $addToSet (set semantics — no duplicates).
    # =========================================================================

    async def add_preferred_specialty(self, patient_id: str, specialty: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$addToSet": {"preferred_specialties": specialty},
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] add_preferred_specialty failed | patient={patient_id} | {exc}")

    # =========================================================================
    # PROFILE — PREFERRED DOCTORS
    # Keeps a list of {id, name, specialty, last_seen} dicts, ordered by
    # last_seen descending, capped at MAX_PREFERRED entries.
    # Uses read-modify-write: pull old entry for same doctor_id then push new.
    # This ensures latest last_seen is always current without duplicates.
    # =========================================================================

    async def upsert_preferred_doctor(
        self,
        patient_id: str,
        doctor: dict[str, Any],
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            col = db[self.PROFILES_COLLECTION]
            # Remove stale entry for same doctor_id (if any)
            await col.update_one(
                {"patient_id": patient_id},
                {"$pull": {"preferred_doctors": {"id": doctor["id"]}}},
            )
            # Push updated entry and keep list capped (most recent first)
            await col.update_one(
                {"patient_id": patient_id},
                {
                    "$push": {
                        "preferred_doctors": {
                            "$each": [doctor],
                            "$slice": -MAX_PREFERRED,
                        }
                    },
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] upsert_preferred_doctor failed | patient={patient_id} | {exc}")

    # =========================================================================
    # PROFILE — PREFERRED TIMES
    # Tracks times the patient has booked successfully. Uses $addToSet.
    # =========================================================================

    async def add_preferred_time(self, patient_id: str, time_str: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$addToSet": {"preferred_times": time_str},
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] add_preferred_time failed | patient={patient_id} | {exc}")

    # =========================================================================
    # PROFILE — UPDATE APPOINTMENT STATUS IN HISTORY
    # Called when an appointment is cancelled or rescheduled.
    # =========================================================================

    async def update_appointment_history_status(
        self,
        patient_id: str,
        appointment_id: str,
        new_status: str,
    ) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {
                    "patient_id": patient_id,
                    "appointment_history.appointment_id": appointment_id,
                },
                {
                    "$set": {
                        "appointment_history.$.status": new_status,
                        "updated_at": now,
                    }
                },
            )
        except Exception as exc:
            logger.error(
                f"[PROFILE REPO] update_appointment_history_status failed | "
                f"patient={patient_id} appt={appointment_id} | {exc}"
            )

    # =========================================================================
    # REMINDER JOBS — CREATE
    # Returns the inserted document id as str, or None on failure.
    # =========================================================================

    async def create_reminder_job(self, job: dict[str, Any]) -> str | None:
        db = get_database()
        if db is None:
            return None
        try:
            result = await db[self.REMINDERS_COLLECTION].insert_one(job)
            return str(result.inserted_id)
        except Exception as exc:
            logger.error(f"[PROFILE REPO] create_reminder_job failed | {exc}")
            return None

    # =========================================================================
    # REMINDER JOBS — CANCEL
    # Marks reminder as cancelled so the future worker skips it.
    # =========================================================================

    async def cancel_reminder_job(self, appointment_id: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            await db[self.REMINDERS_COLLECTION].update_many(
                {"appointment_id": appointment_id, "status": "pending"},
                {
                    "$set": {
                        "status": "cancelled",
                        "cancelled_at": datetime.now(timezone.utc),
                    }
                },
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] cancel_reminder_job failed | appt={appointment_id} | {exc}")

    # =========================================================================
    # PROFILE — RECURRING SYMPTOMS
    # Tracks symptom keywords observed across preconsultation sessions.
    # Uses $addToSet for deduplication — each unique symptom stored once.
    # =========================================================================

    async def add_recurring_symptom(self, patient_id: str, symptom: str) -> None:
        db = get_database()
        if db is None:
            return
        try:
            now = datetime.now(timezone.utc)
            await db[self.PROFILES_COLLECTION].update_one(
                {"patient_id": patient_id},
                {
                    "$addToSet": {"recurring_symptoms": symptom.lower().strip()},
                    "$set": {"updated_at": now},
                    "$setOnInsert": {"patient_id": patient_id, "created_at": now},
                },
                upsert=True,
            )
        except Exception as exc:
            logger.error(f"[PROFILE REPO] add_recurring_symptom failed | patient={patient_id} | {exc}")

    # =========================================================================
    # INDEXES — called once at startup
    # =========================================================================

    async def create_indexes(self) -> None:
        db = get_database()
        if db is None:
            return
        try:
            profiles = db[self.PROFILES_COLLECTION]
            await profiles.create_index("patient_id", unique=True)
            await profiles.create_index("preferred_specialties")
            await profiles.create_index("preferred_doctors.id")

            # The legacy phone_1 index was created as a non-sparse unique index.
            # MongoDB allows only ONE null value in a non-sparse unique index, so
            # every second patient without a phone field fails with E11000.
            # Fix: drop the old index and recreate as sparse+unique.
            # Sparse means only documents that HAVE a non-null phone are indexed;
            # documents with phone=null or no phone field are invisible to the index
            # and coexist freely.  Existing phone values remain uniquely constrained.
            # No data is modified — this is a pure index metadata change.
            try:
                await profiles.drop_index("phone_1")
                logger.info("[PROFILE REPO] dropped legacy non-sparse phone_1 index")
            except Exception:
                pass  # index may not exist on a fresh deployment — safe to ignore
            await profiles.create_index(
                "phone",
                unique=True,
                sparse=True,
                name="phone_sparse_unique",
            )

            reminders = db[self.REMINDERS_COLLECTION]
            await reminders.create_index("appointment_id")
            await reminders.create_index([("status", 1), ("remind_at", 1)])
            logger.info("[PROFILE REPO] indexes ensured")
        except Exception as exc:
            logger.error(f"[PROFILE REPO] create_indexes failed: {exc}")
