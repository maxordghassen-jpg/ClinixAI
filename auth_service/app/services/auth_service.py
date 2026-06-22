import logging
import re
from datetime import datetime, timezone
from typing import Any

from app.core.security import create_access_token, hash_password, verify_password
from app.db.mongo_client import get_database
from app.repositories.user_repository import UserRepository

logger = logging.getLogger(__name__)


class AuthService:

    def __init__(self) -> None:
        self.users = UserRepository()

    # ── Signup (patients only) ────────────────────────────────────────────────

    async def signup_patient(self, email: str, password: str, name: str) -> dict[str, Any] | None:
        existing = await self.users.find_by_email(email)
        if existing:
            return None  # email already taken

        slug = re.sub(r"[^a-z0-9]", "-", email.lower().split("@")[0])
        patient_profile_id = f"patient-{slug}"

        # Create a minimal patient_profiles document for the AI agent.
        # IMPORTANT: check for an existing profile by email first (e.g. a patient
        # seeded via the appointments system with a UUID-based patient_id).  If one
        # exists, reuse its patient_id so the JWT points at the rich document rather
        # than creating a new empty stub that would shadow it.
        db = get_database()
        if db is not None:
            try:
                now = datetime.now(timezone.utc)
                existing_profile = await db["patient_profiles"].find_one(
                    {"email": email.lower()}, {"patient_id": 1}
                )
                if existing_profile:
                    patient_profile_id = existing_profile["patient_id"]
                    logger.warning(
                        "[PROFILE_DEBUG] signup | reusing existing profile | "
                        "email=%r existing_patient_id=%r",
                        email, patient_profile_id,
                    )
                else:
                    await db["patient_profiles"].update_one(
                        {"patient_id": patient_profile_id},
                        {
                            "$setOnInsert": {
                                "patient_id": patient_profile_id,
                                "name": name,
                                "email": email.lower(),
                                "created_at": now,
                                "updated_at": now,
                            }
                        },
                        upsert=True,
                    )
                    logger.warning(
                        "[PROFILE_DEBUG] signup | created patient_profiles stub | "
                        "patient_profile_id=%r email=%r",
                        patient_profile_id, email,
                    )
            except Exception as exc:
                logger.warning("[AUTH] patient_profiles upsert failed | %s", exc)

        now = datetime.now(timezone.utc)
        user_doc = {
            "email": email.lower(),
            "password_hash": hash_password(password),
            "role": "patient",
            "name": name,
            "patient_profile_id": patient_profile_id,
            "doctor_id": None,
            "created_at": now,
            "is_active": True,
        }
        ok = await self.users.create(user_doc)
        if not ok:
            return None

        token = create_access_token({
            "sub": email.lower(),
            "role": "patient",
            "patient_profile_id": patient_profile_id,
            "doctor_id": None,
            "name": name,
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": "patient",
            "name": name,
            "patient_profile_id": patient_profile_id,
            "doctor_id": None,
        }

    # ── Login (patients + doctors) ────────────────────────────────────────────

    async def login(self, email: str, password: str) -> dict[str, Any] | None:
        user = await self.users.find_by_email(email)
        if not user:
            return None
        if not verify_password(password, user["password_hash"]):
            return None
        if not user.get("is_active", True):
            return None

        patient_profile_id = user.get("patient_profile_id")

        # ── Identity-mismatch correction for patient accounts ─────────────────
        # Legacy patient_profiles documents were created by the appointments
        # system and use UUID patient_ids.  The auth_service creates slug-based
        # IDs ("patient-{slug}").  If the stored patient_profile_id doesn't
        # resolve to a real document, fall back to email lookup and permanently
        # correct the user record so future logins are instant.
        if user["role"] == "patient" and patient_profile_id:
            db = get_database()
            if db is not None:
                try:
                    existing = await db["patient_profiles"].find_one(
                        {"patient_id": patient_profile_id}, {"patient_id": 1}
                    )
                    logger.warning(
                        "[PROFILE_DEBUG] login | email=%r stored_id=%r resolved=%s",
                        email, patient_profile_id, existing is not None,
                    )
                    # Always look up by email to detect the shadow-stub case:
                    # signup creates a slug-based empty stub even when a richer
                    # UUID-based document already exists.  If the email-based doc
                    # has a DIFFERENT patient_id, prefer it and permanently fix the
                    # user record so future logins are instant.
                    profile_by_email = await db["patient_profiles"].find_one(
                        {"email": email.lower()}, {"patient_id": 1}
                    )
                    if not existing:
                        # Slug doc missing — use email-based doc if available.
                        if profile_by_email:
                            correct_id = profile_by_email["patient_id"]
                            logger.warning(
                                "[PROFILE_DEBUG] login MISMATCH FIXED (missing slug) | "
                                "email=%r old_id=%r → correct_id=%r",
                                email, patient_profile_id, correct_id,
                            )
                            await db["users"].update_one(
                                {"email": email.lower()},
                                {"$set": {"patient_profile_id": correct_id}},
                            )
                            patient_profile_id = correct_id
                        else:
                            logger.warning(
                                "[PROFILE_DEBUG] login | no profile found by id or email "
                                "for %r — keeping slug id",
                                email,
                            )
                    elif profile_by_email and profile_by_email["patient_id"] != patient_profile_id:
                        # Slug stub exists BUT an email-based doc with a different
                        # (richer, UUID-based) patient_id also exists — the stub is
                        # shadowing it.  UUID docs are canonical; permanently fix the
                        # user record so future logins skip this correction entirely.
                        correct_id = profile_by_email["patient_id"]
                        logger.warning(
                            "[PROFILE_DEBUG] login STUB_SHADOW FIXED | "
                            "email=%r slug_id=%r -> uuid_id=%r",
                            email, patient_profile_id, correct_id,
                        )
                        await db["users"].update_one(
                            {"email": email.lower()},
                            {"$set": {"patient_profile_id": correct_id}},
                        )
                        patient_profile_id = correct_id
                except Exception as exc:
                    logger.error("[PROFILE_DEBUG] login id-fix failed | %s", exc)

        token = create_access_token({
            "sub": user["email"],
            "role": user["role"],
            "patient_profile_id": patient_profile_id,
            "doctor_id": user.get("doctor_id"),
            "name": user.get("name", ""),
        })
        return {
            "access_token": token,
            "token_type": "bearer",
            "role": user["role"],
            "name": user.get("name", ""),
            "patient_profile_id": patient_profile_id,
            "doctor_id": user.get("doctor_id"),
        }

    # ── Current user ──────────────────────────────────────────────────────────

    async def get_current_user(self, email: str) -> dict[str, Any] | None:
        return await self.users.find_by_email(email)
