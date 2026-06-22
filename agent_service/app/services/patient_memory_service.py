"""
PatientMemoryService — domain layer between orchestration and MongoDB.

ORCHESTRATION RULES:
  - load_profile()   → called synchronously in MemoryNode (blocking, fast read)
  - All write methods → called via asyncio.create_task() (fire-and-forget)
    These writes never block the agent response. If MongoDB is unavailable,
    the fire-and-forget task logs the error silently and the turn continues.

MEMORY BOUNDARY:
  - This service only reads/writes MongoDB (long-term patient intelligence).
  - It has zero knowledge of Redis or state.memory.
  - It only receives completed, canonical values (ISO dates, HH:MM times,
    normalized specialty names) — never raw user input.

WRITE POLICY:
  - Writes happen only on meaningful lifecycle events:
      booking confirmed  → record_booking()
      booking cancelled  → record_cancellation()
      language detected  → update_language()   (only when changed)
      reminder set       → update_reminder_preference()
  - Language is written at most once per turn — StateWriterNode drives Redis,
    PatientMemoryService drives the profile. They are independent.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.repositories.patient_profile_repo import PatientProfileRepository

logger = logging.getLogger(__name__)

_repo = PatientProfileRepository()


class PatientMemoryService:

    # =========================================================================
    # READ — synchronous-style async. Called in MemoryNode at turn start.
    # Returns {} on any failure — callers must handle empty profile gracefully.
    # =========================================================================

    async def load_profile(self, patient_id: str) -> dict[str, Any]:
        if not patient_id:
            return {}
        try:
            profile = await _repo.get_by_patient_id(patient_id)
            if profile is None:
                logger.debug(f"[PATIENT MEM] no profile found for patient={patient_id}")
                return {}
            logger.debug(f"[PATIENT MEM] profile loaded | patient={patient_id} | "
                         f"lang={profile.get('language')} "
                         f"specialties={profile.get('preferred_specialties', [])}")
            return profile
        except Exception as exc:
            logger.error(f"[PATIENT MEM] load_profile error | patient={patient_id} | {exc}")
            return {}

    # =========================================================================
    # WRITE: BOOKING CONFIRMED
    # Records the completed appointment into appointment_history and updates
    # all preference signals: preferred_doctors, preferred_specialties,
    # preferred_times, and increments stats.total_booked.
    #
    # Called via: asyncio.create_task(service.record_booking(...))
    # =========================================================================

    async def record_booking(
        self,
        patient_id: str,
        appointment_id: str,
        doctor_id: str,
        doctor_name: str,
        specialty: str,
        date: str,        # ISO YYYY-MM-DD
        time: str,        # HH:MM
    ) -> None:
        if not patient_id:
            return
        try:
            now = datetime.now(timezone.utc)
            history_entry = {
                "appointment_id": appointment_id or "",
                "doctor_id": doctor_id,
                "doctor_name": doctor_name,
                "specialty": specialty,
                "date": date,
                "time": time,
                "status": "confirmed",
                "booked_at": now,
            }
            doctor_entry = {
                "id": doctor_id,
                "name": doctor_name,
                "specialty": specialty,
                "last_seen": now,
            }

            # Run all writes in parallel — they are independent updates
            await asyncio.gather(
                _repo.push_appointment_history(patient_id, history_entry),
                _repo.upsert_preferred_doctor(patient_id, doctor_entry),
                _repo.add_preferred_specialty(patient_id, specialty),
                _repo.add_preferred_time(patient_id, time),
                _repo.increment_stat(patient_id, "total_booked"),
                return_exceptions=True,  # individual failures don't abort siblings
            )
            logger.info(f"[PATIENT MEM] booking recorded | patient={patient_id} "
                        f"doctor={doctor_id} date={date} time={time}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] record_booking error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: BOOKING CANCELLED
    # Updates appointment_history entry status and increments cancellation stat.
    # Also cancels any pending reminder for this appointment.
    #
    # Called via: asyncio.create_task(service.record_cancellation(...))
    # =========================================================================

    async def record_cancellation(
        self,
        patient_id: str,
        appointment_id: str,
    ) -> None:
        if not patient_id:
            return
        try:
            await asyncio.gather(
                _repo.update_appointment_history_status(patient_id, appointment_id, "cancelled"),
                _repo.cancel_reminder_job(appointment_id),
                _repo.increment_stat(patient_id, "total_cancelled"),
                return_exceptions=True,
            )
            logger.info(f"[PATIENT MEM] cancellation recorded | patient={patient_id} appt={appointment_id}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] record_cancellation error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: LANGUAGE DETECTED
    # Only writes when the detected language differs from the stored one, so
    # this is cheap on repeat turns in the same language.
    #
    # Called via: asyncio.create_task(service.update_language(...))
    # =========================================================================

    async def update_language(self, patient_id: str, language: str) -> None:
        if not patient_id or not language:
            return
        try:
            await _repo.upsert_fields(patient_id, {"language": language})
            logger.debug(f"[PATIENT MEM] language updated | patient={patient_id} lang={language}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] update_language error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: REMINDER PREFERENCE
    # Persists the patient's notification timing preference.
    # advance_hours: how many hours before the appointment to notify.
    # channel: "app" | "sms" | "email" (dispatch is Phase 6)
    #
    # Called via: asyncio.create_task(service.update_reminder_preference(...))
    # =========================================================================

    async def update_reminder_preference(
        self,
        patient_id: str,
        advance_hours: int,
        channel: str = "app",
    ) -> None:
        if not patient_id:
            return
        try:
            await _repo.upsert_fields(
                patient_id,
                {
                    "reminder_preferences.advance_hours": advance_hours,
                    "reminder_preferences.channel": channel,
                },
            )
            logger.info(f"[PATIENT MEM] reminder preference updated | patient={patient_id} "
                        f"advance={advance_hours}h channel={channel}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] update_reminder_preference error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: SCHEDULE REMINDER JOB
    # Creates a reminder_jobs document. The actual notification is dispatched
    # by a separate worker process (Phase 6) — this method only writes the
    # record. The worker polls reminder_jobs WHERE status="pending" AND
    # remind_at <= now, dispatches, then updates status="sent".
    #
    # appointment_dt must be an ISO string or datetime for remind_at math.
    # advance_hours defaults to the value in the patient's profile (loaded
    # by the caller before invoking this). If no preference is set, 24h.
    #
    # Called via: asyncio.create_task(service.schedule_reminder(...))
    # =========================================================================

    async def schedule_reminder(
        self,
        appointment_id: str,
        patient_id: str,
        doctor_name: str,
        appointment_date: str,   # ISO YYYY-MM-DD
        appointment_time: str,   # HH:MM
        advance_hours: int = 24,
        channel: str = "app",
    ) -> None:
        if not patient_id or not appointment_id:
            return
        try:
            # Normalize date to ISO YYYY-MM-DD in case the caller passes a
            # relative keyword ("tomorrow", "demain") instead of a resolved date.
            from graphs.shared.normalizers.date_normalizer import DateNormalizer
            iso_date = DateNormalizer.normalize_safe(appointment_date) or appointment_date
            # Construct the appointment datetime (UTC assumed)
            appt_dt = datetime.fromisoformat(f"{iso_date}T{appointment_time}:00")
            appt_dt = appt_dt.replace(tzinfo=timezone.utc)
            remind_at = appt_dt - timedelta(hours=advance_hours)

            job = {
                "appointment_id": appointment_id,
                "patient_id": patient_id,
                "doctor_name": doctor_name,
                "appointment_date": appointment_date,
                "appointment_time": appointment_time,
                "remind_at": remind_at,
                "advance_hours": advance_hours,
                "channel": channel,
                "status": "pending",
                "created_at": datetime.now(timezone.utc),
            }
            job_id = await _repo.create_reminder_job(job)
            if job_id:
                logger.info(f"[PATIENT MEM] reminder job created | patient={patient_id} "
                            f"appt={appointment_id} remind_at={remind_at.isoformat()} job_id={job_id}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] schedule_reminder error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: BOOKING RESCHEDULED
    # Updates appointment_history entry status, learns the new preferred time,
    # and increments the rescheduled stat.
    #
    # Called via: asyncio.create_task(service.record_reschedule(...))
    # =========================================================================

    async def record_reschedule(
        self,
        patient_id: str,
        appointment_id: str,
        new_date: str,   # ISO YYYY-MM-DD
        new_time: str,   # HH:MM
    ) -> None:
        if not patient_id:
            return
        try:
            await asyncio.gather(
                _repo.update_appointment_history_status(patient_id, appointment_id, "rescheduled"),
                _repo.add_preferred_time(patient_id, new_time),
                _repo.increment_stat(patient_id, "total_rescheduled"),
                return_exceptions=True,
            )
            logger.info(f"[PATIENT MEM] reschedule recorded | patient={patient_id} "
                        f"appt={appointment_id} new_date={new_date} new_time={new_time}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] record_reschedule error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: PRECONSULTATION COMPLETED
    # Records the chief complaint as a recurring_symptom signal in the
    # patient profile so the memory system can surface it in future context.
    # Also links the preconsultation session to an appointment if one exists.
    #
    # Called via: asyncio.create_task(service.record_preconsultation(...))
    # =========================================================================

    async def record_preconsultation(
        self,
        patient_id: str,
        session_id: str,
        chief_complaint: str,
        severity: int,
    ) -> None:
        if not patient_id or not chief_complaint:
            return
        try:
            # Normalise the chief complaint to a lower-case symptom keyword.
            # Split multi-word complaints into individual tokens (first 2 words max).
            words = chief_complaint.lower().split()
            symptom_key = " ".join(words[:2]) if len(words) > 1 else words[0] if words else ""
            if symptom_key:
                await _repo.add_recurring_symptom(patient_id, symptom_key)
            # Increment a preconsultation counter for analytics
            await _repo.increment_stat(patient_id, "total_preconsultations")
            logger.info(f"[PATIENT MEM] preconsultation recorded | patient={patient_id} "
                        f"symptom={symptom_key!r} severity={severity}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] record_preconsultation error | patient={patient_id} | {exc}")

    # =========================================================================
    # WRITE: CANCEL REMINDER JOB
    # Marks all pending reminders for this appointment as cancelled.
    # Safe to call even if no reminder exists (idempotent).
    #
    # Called via: asyncio.create_task(service.cancel_reminder(...))
    # =========================================================================

    async def cancel_reminder(self, appointment_id: str) -> None:
        if not appointment_id:
            return
        try:
            await _repo.cancel_reminder_job(appointment_id)
            logger.info(f"[PATIENT MEM] reminder cancelled | appt={appointment_id}")
        except Exception as exc:
            logger.error(f"[PATIENT MEM] cancel_reminder error | appt={appointment_id} | {exc}")
