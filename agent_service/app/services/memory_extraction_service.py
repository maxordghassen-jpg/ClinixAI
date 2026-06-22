"""
MemoryExtractionService — extracts structured, longitudinal memories from completed turns.

Called as fire-and-forget after StateWriterNode flushes Redis. Analyzes the session
memory snapshot for confident, durable facts and upserts them into user_memories.

Two-phase operation:
  Phase 1 (sync):  rule-based extraction → structured key/value memories → upsert to MongoDB
  Phase 2 (async): embedding generation → vector stored on each memory document

Precision rules (what NOT to extract):
  - Trivial messages ("ok", "1", "yes") contain no persistent signal — skip entirely.
  - Messages shorter than MIN_MESSAGE_LEN chars are too sparse to be meaningful.
  - Memories below MIN_CONFIDENCE are discarded before storage.
  - doctor_affinity requires BOTH doctor_id AND doctor_name (reject ID-only matches).
  - specialty_interest only extracted during active booking/search workflow steps.

Phase 2 runs as a separate async batch after Phase 1, throttled to _EMBED_THROTTLE
new vectors per turn.

Memory types extracted:
  profile   — durable preferences (language, specialty interest, time of day, location,
               doctor affinity, place type)
  episodic  — concrete past events (last booked doctor)
  workflow  — NOT stored here — workflow state lives in workflow_snapshots via MemoryManager
"""

import logging
from datetime import datetime, timezone
from typing import Any

from app.repositories.memory_repo import MemoryRepository

logger = logging.getLogger(__name__)

_repo = MemoryRepository()

# ── Precision thresholds ──────────────────────────────────────────────────────

MIN_MESSAGE_LEN = 3      # characters — skip one-word noise like "ok", "1"
MIN_CONFIDENCE  = 0.55   # global floor — discard low-confidence memories

# Messages that signal no new information (agreement, navigation, acknowledgement)
_TRIVIAL_MESSAGES: frozenset[str] = frozenset({
    # English
    "ok", "okay", "yes", "no", "sure", "alright", "fine", "thanks", "thank you",
    "got it", "understood", "correct", "right", "yep", "nope",
    "1", "2", "3", "4", "5",
    # French
    "oui", "non", "merci", "d'accord", "parfait", "bien", "ok", "super",
    "1", "2", "3",
    # Arabic
    "نعم", "لا", "شكرا", "حسنا", "موافق", "تمام",
})

# Workflow steps where a specialty mention is meaningful for extraction
_SPECIALTY_EXTRACTION_STEPS: frozenset[str] = frozenset({
    "awaiting_specialty",
    "searching_doctors",
    "selecting_doctor",
    "doctor_selected",
    "awaiting_date",
    "awaiting_time",
    "awaiting_slot_selection",
    "ready_to_book",
    "confirmed",
})

# Time-of-day token sets for preference extraction
_MORNING_TOKENS   = frozenset({"morning", "matin", "صباح", "9am", "10am", "11am"})
_AFTERNOON_TOKENS = frozenset({"afternoon", "après-midi", "بعد الظهر", "2pm", "3pm", "4pm"})
_EVENING_TOKENS   = frozenset({"evening", "soir", "مساء", "5pm", "6pm", "7pm"})

# Max embeddings generated per fire-and-forget call (performance guard)
_EMBED_THROTTLE = 5


class MemoryExtractionService:

    async def extract_and_store(
        self,
        user_id: str,
        role: str,
        message: str,
        response: str,
        session_memory: dict[str, Any],
        profile: dict[str, Any],
    ) -> None:
        if not user_id:
            return
        if _is_low_value_message(message):
            logger.debug(f"[MEM EXTRACT] trivial message skipped | user={user_id}")
            return
        try:
            memories = self._extract(message, response, session_memory, role)
            # Apply global confidence floor before any storage
            memories = [m for m in memories if m.get("confidence", 0) >= MIN_CONFIDENCE]

            for m in memories:
                await _repo.upsert_memory(
                    user_id=user_id,
                    role=role,
                    memory_type=m["type"],
                    key=m["key"],
                    value=m["value"],
                    confidence=m["confidence"],
                    source=m.get("source", "chat"),
                )
            if memories:
                logger.debug(
                    f"[MEM EXTRACT] {len(memories)} memories stored | user={user_id} "
                    f"keys={[m['key'] for m in memories]}"
                )

            if memories:
                await self._embed_and_store(user_id, memories)

        except Exception as exc:
            logger.error(f"[MEM EXTRACT] extract_and_store error | user={user_id} | {exc}")

    # ── Embedding phase ───────────────────────────────────────────────────────

    async def _embed_and_store(
        self,
        user_id: str,
        memories: list[dict[str, Any]],
    ) -> None:
        """Batch-embed extracted memories and persist vectors."""
        try:
            from app.embeddings.embed_service import EmbedService
            svc    = EmbedService()
            tuples = await svc.embed_memories_batch(memories, throttle=_EMBED_THROTTLE)
            stored = 0
            for key, _value, vec in tuples:
                if vec:
                    await _repo.update_embedding(user_id, key, vec)
                    stored += 1
            if stored:
                logger.debug(f"[MEM EXTRACT] {stored} embeddings stored | user={user_id}")
        except Exception as exc:
            logger.debug(f"[MEM EXTRACT] embedding phase skipped: {exc}")

    # ── Rule-based extraction ─────────────────────────────────────────────────

    def _extract(
        self,
        message: str,
        response: str,
        session_memory: dict[str, Any],
        role: str,
    ) -> list[dict[str, Any]]:
        memories: list[dict[str, Any]] = []
        msg  = message.lower()
        step = session_memory.get("step", "")

        # ── Profile: language ────────────────────────────────────────────────
        lang = session_memory.get("language")
        if lang and lang not in ("unknown", "", None):
            memories.append({
                "type": "profile", "key": "language", "value": lang,
                "confidence": 0.9, "source": "chat",
            })

        # ── Profile: specialty interest ────────────────────────────────────
        # Only extract when inside an active booking/search workflow so that
        # a passing mention like "my cardiologist" doesn't inflate specialty scores.
        specialty = session_memory.get("specialty")
        if specialty and (step in _SPECIALTY_EXTRACTION_STEPS or not step):
            memories.append({
                "type":  "profile",
                "key":   f"specialty_interest:{specialty}",
                "value": specialty,
                "confidence": 0.75,
                "source": "chat",
            })

        # ── Profile: preferred appointment time ───────────────────────────────
        booked_time = session_memory.get("time")
        if booked_time and step in ("ready_to_book", "confirmed"):
            memories.append({
                "type": "profile", "key": "preferred_time",
                "value": booked_time, "confidence": 0.8, "source": "booking",
            })

        # ── Profile: time-of-day preference ───────────────────────────────────
        tokens = set(msg.split())
        if tokens & _MORNING_TOKENS:
            memories.append({
                "type": "profile", "key": "preferred_time_of_day",
                "value": "morning", "confidence": 0.7, "source": "chat",
            })
        elif tokens & _AFTERNOON_TOKENS:
            memories.append({
                "type": "profile", "key": "preferred_time_of_day",
                "value": "afternoon", "confidence": 0.7, "source": "chat",
            })
        elif tokens & _EVENING_TOKENS:
            memories.append({
                "type": "profile", "key": "preferred_time_of_day",
                "value": "evening", "confidence": 0.7, "source": "chat",
            })

        # ── Profile: location / area preference ───────────────────────────────
        location = session_memory.get("location") or session_memory.get("governorate")
        if location and isinstance(location, str) and len(location) >= 2:
            memories.append({
                "type": "profile", "key": "preferred_location",
                "value": location, "confidence": 0.65, "source": "geo_search",
            })

        # ── Profile: geo place-type preference ────────────────────────────────
        place_type = session_memory.get("place_type")
        if place_type and session_memory.get("intent") == "geo_search":
            memories.append({
                "type": "profile", "key": f"preferred_place_type:{place_type}",
                "value": place_type, "confidence": 0.6, "source": "geo_search",
            })

        # ── Profile: doctor affinity ───────────────────────────────────────────
        # Require both ID and a non-empty name — reject ID-only or name-only matches.
        doctor_id   = session_memory.get("doctor_id")
        doctor_name = session_memory.get("doctor_name")
        if (
            doctor_id and isinstance(doctor_id, str)
            and doctor_name and isinstance(doctor_name, str)
            and len(doctor_name) >= 2
        ):
            memories.append({
                "type": "profile",
                "key":  f"doctor_affinity:{doctor_id}",
                "value": {
                    "doctor_id":   doctor_id,
                    "doctor_name": doctor_name,
                    "specialty":   session_memory.get("specialty", ""),
                },
                "confidence": 0.8,
                "source": "chat",
            })

        # ── Episodic: completed booking ────────────────────────────────────────
        if step in ("ready_to_book", "confirmed") and doctor_id and doctor_name:
            memories.append({
                "type": "episodic",
                "key":  "last_booked_doctor",
                "value": {
                    "doctor_id":   doctor_id,
                    "doctor_name": doctor_name,
                    "specialty":   session_memory.get("specialty", ""),
                    "date":        session_memory.get("date", ""),
                    "time":        session_memory.get("time", ""),
                    "booked_at":   datetime.now(timezone.utc).isoformat(),
                },
                "confidence": 0.95,
                "source": "booking",
            })

        # ── Doctor-role: frequent intent patterns ──────────────────────────────
        if role == "doctor":
            intent = session_memory.get("intent")
            if intent and intent not in ("none", ""):
                memories.append({
                    "type": "profile",
                    "key":  f"frequent_intent:{intent}",
                    "value": intent,
                    "confidence": 0.6,
                    "source": "chat",
                })

        return memories


# ── Module-level helpers ──────────────────────────────────────────────────────

def _is_low_value_message(message: str) -> bool:
    """
    Return True if the message carries no extractable persistent signal.
    Trivial messages (acknowledgements, single digits, ultra-short replies)
    should not trigger memory extraction.
    """
    stripped = message.strip().lower()
    if len(stripped) < MIN_MESSAGE_LEN:
        return True
    return stripped in _TRIVIAL_MESSAGES
