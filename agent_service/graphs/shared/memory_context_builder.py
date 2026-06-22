"""
MemoryContextBuilder — converts structured + semantic memories into a compact
prompt-injectable string.

Reads from:
  state.profile            — patient_profiles document
  state.long_term_memories — structured user_memories (frequency/confidence ranked)
  semantic                 — EmbedService-ranked list with retrieval_meta (per-turn)

Priority order:
  1. Semantic memories (hybrid-scored, directly relevant to current message)
  2. Patient profile fields (preferred doctors, specialties, times)
  3. Remaining long-term memories not yet covered

Hard limits:
  _MAX_CONTEXT_LINES — line count cap  (12 lines)
  _MAX_CONTEXT_CHARS — character cap   (900 chars, ~225 tokens)

Explainability metadata (retrieval_meta.similarity, matched_topic, hybrid_score)
is stored on each memory object and surfaced in the frontend and API responses.
It is NOT injected into the LLM prompt — the model doesn't benefit from seeing
similarity scores, and omitting them keeps prompt size minimal.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Hard caps on what gets injected into the LLM prompt
_MAX_CONTEXT_LINES = 12
_MAX_CONTEXT_CHARS = 900   # ~225 tokens

# Minimum semantic similarity to include a memory in the LLM context.
# This is stricter than MemoryManager's retrieval threshold (0.30) because
# the context builder only wants high-confidence semantic matches in the prompt.
_MIN_CONTEXT_SIM = 0.40


class MemoryContextBuilder:

    @staticmethod
    def build_patient_context(
        profile: dict[str, Any],
        long_term: list[dict[str, Any]],
        semantic: list[dict[str, Any]] | None = None,
    ) -> str:
        lines:     list[str] = []
        seen_keys: set[str]  = set()

        # ── 1. Semantic-ranked memories (hybrid score, most contextually relevant) ─
        if semantic:
            for mem in semantic:
                if len(lines) >= _MAX_CONTEXT_LINES:
                    break
                key  = mem.get("key", "")
                val  = mem.get("value")
                sim  = mem.get("retrieval_meta", {}).get("similarity", 0.0)

                # Only inject if above the context-quality threshold
                if sim < _MIN_CONTEXT_SIM:
                    continue
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                line = _format_memory_line(key, val)
                if line:
                    lines.append(line)

        # ── 2a. Medical profile — safety-critical fields first ────────────────
        if len(lines) < _MAX_CONTEXT_LINES:
            allergies = profile.get("allergies", [])
            if allergies and "_allergies" not in seen_keys:
                seen_keys.add("_allergies")
                lines.append(f"Known allergies: {', '.join(allergies)}")

            conditions = profile.get("chronic_conditions", [])
            if conditions and "_conditions" not in seen_keys:
                seen_keys.add("_conditions")
                lines.append(f"Chronic conditions: {', '.join(conditions)}")

            meds = profile.get("current_medications", [])
            if meds and "_meds" not in seen_keys:
                seen_keys.add("_meds")
                lines.append(f"Current medications: {', '.join(meds[:3])}")

            blood_type = profile.get("blood_type")
            if blood_type and "_bt" not in seen_keys:
                seen_keys.add("_bt")
                lines.append(f"Blood type: {blood_type}")

        # ── 2b. Structured memories from patient_profiles ─────────────────────
        if len(lines) < _MAX_CONTEXT_LINES:
            preferred_doctors = profile.get("preferred_doctors", [])
            if preferred_doctors:
                top  = preferred_doctors[-1]
                name = top.get("name", "")
                spec = top.get("specialty", "")
                pkey = f"_pd_{name}"
                if name and pkey not in seen_keys:
                    seen_keys.add(pkey)
                    lines.append(
                        f"Previously visited: {name}" + (f" ({spec})" if spec else "")
                    )

            preferred_specialties = profile.get("preferred_specialties", [])
            if preferred_specialties and "_ps" not in seen_keys:
                seen_keys.add("_ps")
                lines.append(f"Frequent specialties: {', '.join(preferred_specialties[:3])}")

            preferred_times = profile.get("preferred_times", [])
            if preferred_times and "_pt" not in seen_keys:
                seen_keys.add("_pt")
                lines.append(f"Usual appointment times: {', '.join(list(preferred_times)[:3])}")

            lang = profile.get("language")
            if lang and lang not in ("unknown", "", None) and "language" not in seen_keys:
                seen_keys.add("language")
                lines.append(f"Preferred language: {lang}")

            recurring = profile.get("recurring_symptoms", [])
            if recurring and "_recurring" not in seen_keys and len(lines) < _MAX_CONTEXT_LINES:
                seen_keys.add("_recurring")
                lines.append(f"Recurring symptoms: {', '.join(list(recurring)[:4])}")

            history = profile.get("appointment_history", [])
            if history:
                last = history[-1]
                doc  = last.get("doctor_name", "")
                date = last.get("date", "")
                pkey = f"_la_{doc}"
                if doc and pkey not in seen_keys:
                    seen_keys.add(pkey)
                    lines.append(
                        f"Last appointment: {doc}" + (f" on {date}" if date else "")
                    )

        # ── 3. Long-term user_memories (structured, fills remaining slots) ─────
        for mem in long_term:
            if len(lines) >= _MAX_CONTEXT_LINES:
                break
            key = mem.get("key", "")
            val = mem.get("value")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            line = _format_memory_line(key, val)
            if line:
                lines.append(line)

        if not lines:
            return ""

        context = "Patient context (use for personalization):\n" + "\n".join(
            f"- {l}" for l in lines
        )

        # Hard character cap — truncate at the last complete line
        if len(context) > _MAX_CONTEXT_CHARS:
            context = context[:_MAX_CONTEXT_CHARS].rsplit("\n", 1)[0]
            logger.debug(f"[CTX BUILDER] context truncated to {len(context)} chars")

        return context

    @staticmethod
    def build_doctor_context(
        profile: dict[str, Any],
        long_term: list[dict[str, Any]],
        semantic: list[dict[str, Any]] | None = None,
    ) -> str:
        lines:     list[str] = []
        seen_keys: set[str]  = set()
        _CAP = 6

        if semantic:
            for mem in (semantic or [])[:3]:
                key = mem.get("key", "")
                val = mem.get("value")
                sim = mem.get("retrieval_meta", {}).get("similarity", 0.0)
                if sim < _MIN_CONTEXT_SIM or key in seen_keys:
                    continue
                seen_keys.add(key)
                line = _format_memory_line(key, val)
                if line:
                    lines.append(line)

        for mem in long_term[:8]:
            if len(lines) >= _CAP:
                break
            key = mem.get("key", "")
            val = mem.get("value")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            if key.startswith("frequent_intent:") and val:
                lines.append(f"Frequently uses: {val} (freq={mem.get('frequency', 1)})")

        if not lines:
            return ""
        return "Doctor context:\n" + "\n".join(f"- {l}" for l in lines)

    @staticmethod
    def build_resume_hint(pending_workflow: dict[str, Any] | None) -> str:
        if not pending_workflow:
            return ""
        ctx   = pending_workflow.get("context", {})
        wtype = pending_workflow.get("workflow_type", "workflow")
        step  = pending_workflow.get("step", "")

        parts: list[str] = []
        if ctx.get("specialty"):
            parts.append(f"specialty={ctx['specialty']}")
        if ctx.get("doctor_name"):
            parts.append(f"doctor={ctx['doctor_name']}")
        if ctx.get("date"):
            parts.append(f"date={ctx['date']}")
        detail = ", ".join(parts)
        return (
            f"Unfinished {wtype} from last session (step={step!r}"
            + (f", {detail}" if detail else "")
            + "). Ask if the user wants to resume."
        )

    @staticmethod
    def build_doctor_recommendations(
        long_term: list[dict[str, Any]],
        semantic: list[dict[str, Any]] | None = None,
        current_specialty: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return up to 3 doctor recommendation candidates ranked by affinity.

        Scoring:
          base  = min(frequency / 10, 1.0) × 0.6  +  semantic_sim × 0.4
          bonus = +0.25 if specialty matches current_specialty

        Only candidates with confidence ≥ 0.6 are included (filters out
        single low-quality doctor mentions).
        """
        candidates: dict[str, dict[str, Any]] = {}

        all_memories = list(long_term) + list(semantic or [])

        for mem in all_memories:
            key   = mem.get("key", "")
            value = mem.get("value")

            if key.startswith("doctor_affinity:") and isinstance(value, dict):
                doc_id   = value.get("doctor_id", "")
                doc_name = value.get("doctor_name", "")
                spec     = value.get("specialty", "")
                conf     = mem.get("confidence", 0.0)

                if not doc_id or not doc_name or conf < 0.6:
                    continue

                freq  = mem.get("frequency", 1)
                sim   = mem.get("retrieval_meta", {}).get("similarity", 0.0)
                score = min(freq / 10.0, 1.0) * 0.6 + sim * 0.4

                if current_specialty and spec and current_specialty.lower() in spec.lower():
                    score += 0.25

                score = round(min(score, 1.0), 3)

                if doc_id not in candidates or candidates[doc_id]["score"] < score:
                    candidates[doc_id] = {
                        "doctor_id":   doc_id,
                        "doctor_name": doc_name,
                        "specialty":   spec,
                        "score":       score,
                        "visit_count": freq,
                        "reason":      _recommendation_reason(freq, sim, current_specialty, spec),
                    }

            elif key == "last_booked_doctor" and isinstance(value, dict):
                doc_id   = value.get("doctor_id", "")
                doc_name = value.get("doctor_name", "")
                spec     = value.get("specialty", "")
                if not doc_id or not doc_name or doc_id in candidates:
                    continue
                candidates[doc_id] = {
                    "doctor_id":   doc_id,
                    "doctor_name": doc_name,
                    "specialty":   spec,
                    "score":       0.45,
                    "visit_count": 1,
                    "reason":      "Last booked doctor",
                }

        ranked = sorted(candidates.values(), key=lambda x: x["score"], reverse=True)
        return ranked[:3]


# ── Memory line formatter ─────────────────────────────────────────────────────

def _format_memory_line(key: str, value: Any) -> str:
    """Render a single memory key/value as a concise one-line prompt string."""

    if key == "preferred_time_of_day" and value:
        return f"Prefers {value} appointments"

    if key == "preferred_location" and value:
        return f"Preferred area: {value}"

    if key == "last_booked_doctor" and isinstance(value, dict):
        doc  = value.get("doctor_name", "")
        spec = value.get("specialty", "")
        date = value.get("date", "")
        if doc:
            return (
                f"Last booked: {doc}"
                + (f" ({spec})" if spec else "")
                + (f" on {date}" if date else "")
            )

    if key == "preferred_time" and value:
        return f"Preferred booking time: {value}"

    if key == "language" and value:
        return f"Preferred language: {value}"

    if key.startswith("specialty_interest:") and value:
        spec = key[len("specialty_interest:"):]
        return f"Interest in {spec}"

    if key.startswith("doctor_affinity:") and isinstance(value, dict):
        doc  = value.get("doctor_name", "")
        spec = value.get("specialty", "")
        if doc:
            return f"Visited: {doc}" + (f" ({spec})" if spec else "")

    if key.startswith("preferred_place_type:") and value:
        place = key[len("preferred_place_type:"):]
        return f"Searches for {place} nearby"

    return ""


# ── Recommendation reason builder ─────────────────────────────────────────────

def _recommendation_reason(
    freq: int, sim: float, query_spec: str | None, doc_spec: str
) -> str:
    parts: list[str] = []
    if freq >= 3:
        parts.append(f"visited {freq}×")
    elif freq >= 2:
        parts.append("visited before")
    if sim >= 0.55:
        parts.append("semantically matched")
    if query_spec and doc_spec and query_spec.lower() in doc_spec.lower():
        parts.append("specialty match")
    return ", ".join(parts) or "past visit"
