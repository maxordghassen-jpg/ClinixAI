"""
EmbedService — orchestration layer between callers and the embedding provider.

Responsibilities:
  1. Normalise memory key/value pairs into embeddable natural-language text.
  2. Check the process-wide LRU cache before calling the provider.
  3. Delegate to the configured EmbeddingProvider (sentence-transformer or OpenAI).
  4. Store results back in the cache.
  5. Compute cosine similarity and hybrid scores.
  6. Rank memories by hybrid score against a query vector.

Graceful degradation:
  Every method returns empty vectors / empty lists on any provider failure.
  Callers degrade to structured-only memory ranking without crashing.

Multilingual behaviour (paraphrase-multilingual-MiniLM-L12-v2):
  The model maps these into nearby embedding clusters regardless of language:
    "cardiologist"  ↔  "cardiologue"       ↔  "طبيب القلب"
    "dermatologist" ↔  "dermatologue"      ↔  "طبيب الجلد"
    "morning"       ↔  "matin"             ↔  "صباح"
    "pharmacy"      ↔  "pharmacie"         ↔  "صيدلية"
  Cross-lingual queries therefore retrieve semantically correct memories
  regardless of the language used in the original conversation.

Performance notes:
  - Query embedding: ~2 ms warm (cached), ~120 ms cold (first model load).
  - Batch embedding of 5 new memories: ~10–30 ms warm.
  - Cosine similarity over 50 × 384-dim vectors: ~0.5 ms in Python.
  - Total added latency per turn (warm): ~3–5 ms.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, Optional

from app.embeddings.cache import get_cached, put_cached, log_cache_stats

logger = logging.getLogger(__name__)

# Per-turn throttle on new provider calls (cache hits don't count)
_EMBED_THROTTLE = 5


# ── Memory text serialisation ─────────────────────────────────────────────────

def memory_to_text(key: str, value: Any) -> str:
    """
    Convert a structured memory key/value to embeddable English text.

    English is intentionally used even for French/Arabic data — the multilingual
    model maps concepts cross-lingually, so "patient prefers cardiologue" and
    "patient prefers cardiologist" land in the same embedding cluster.
    Using consistent English phrases makes the embedding space more uniform.
    """
    if key.startswith("specialty_interest:"):
        spec = key[len("specialty_interest:"):]
        return f"patient prefers {spec} specialist"

    if key.startswith("doctor_affinity:"):
        if isinstance(value, dict):
            name = value.get("doctor_name", "")
            spec = value.get("specialty", "")
            return f"visits doctor {name} {spec}".strip()
        return f"visits doctor {value}"

    if key.startswith("frequent_intent:"):
        intent = key[len("frequent_intent:"):]
        return f"frequently performs {intent.replace('_', ' ')}"

    if key.startswith("preferred_place_type:"):
        place = key[len("preferred_place_type:"):]
        return f"prefers searching for {place} near me"

    if key == "last_booked_doctor":
        if isinstance(value, dict):
            name = value.get("doctor_name", "")
            spec = value.get("specialty", "")
            return f"last booked appointment with {name} {spec}".strip()
        return "completed appointment booking"

    if key == "preferred_time_of_day":
        return f"prefers {value} appointments"

    if key == "preferred_time":
        return f"prefers booking at {value}"

    if key == "preferred_location":
        return f"preferred clinic area {value}"

    if key == "language":
        return f"communicates in {value}"

    # Generic fallback
    clean = key.replace("_", " ").replace(":", " ").strip()
    if isinstance(value, str) and value:
        return f"{clean} {value}".strip()
    if isinstance(value, dict):
        parts = [str(v) for v in value.values() if v and isinstance(v, (str, int, float))]
        return (clean + " " + " ".join(parts[:3])).strip()
    return clean


def topic_from_key(key: str) -> str:
    """Human-readable topic label for retrieval explainability metadata."""
    if key.startswith("specialty_interest:"):
        return key[len("specialty_interest:"):]
    if key.startswith("doctor_affinity:"):
        return "doctor preference"
    if key.startswith("frequent_intent:"):
        return key[len("frequent_intent:"):].replace("_", " ")
    if key.startswith("preferred_place_type:"):
        return "place type preference"
    _MAP = {
        "preferred_time_of_day": "appointment timing",
        "preferred_time":        "appointment time",
        "preferred_location":    "location preference",
        "last_booked_doctor":    "past booking",
        "language":              "communication language",
    }
    return _MAP.get(key, key.replace("_", " "))


# ── Scoring helpers ───────────────────────────────────────────────────────────

def cosine_similarity(a: list[float], b: list[float]) -> float:
    """
    Cosine similarity between two vectors.
    Vectors from SentenceTransformer with normalize_embeddings=True are L2-normalised,
    making this equivalent to the dot product (faster, but norms computed anyway for
    safety when provider is OpenAI or a raw custom model).
    """
    if not a or not b or len(a) != len(b):
        return 0.0
    dot    = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _recency_score(updated_at: Any) -> float:
    """1.0 = updated today, decays linearly to 0.1 at 30 days, floor 0.1."""
    if not updated_at:
        return 0.5
    if isinstance(updated_at, str):
        try:
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        except ValueError:
            return 0.5
    now = datetime.now(timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = max(0, (now - updated_at).days)
    return max(0.1, 1.0 - days / 30.0)


def hybrid_score(
    semantic_sim: float,
    frequency: int,
    confidence: float,
    updated_at: Any,
) -> float:
    """
    Weighted combination of semantic relevance, usage frequency, confidence,
    and recency.

    Weights tuned for healthcare memory patterns:
      0.45 × semantic_sim  — primary signal when the query is relevant
      0.25 × frequency     — rewards recurring preferences (normalised to 10 visits = 1.0)
      0.20 × confidence    — rewards high-certainty extractions
      0.10 × recency       — mild boost for recently observed preferences

    When semantic_sim = 0 (no embedding or below threshold), the score reduces
    to a pure structured rank: 0.25·freq + 0.20·conf + 0.10·recency ≤ 0.55,
    which keeps non-semantic memories below the context injection threshold
    (handled by MemoryContextBuilder._MIN_CONTEXT_SIM = 0.40).
    """
    freq_norm = min(frequency / 10.0, 1.0)
    recency   = _recency_score(updated_at)
    return (
        0.45 * semantic_sim
        + 0.25 * freq_norm
        + 0.20 * confidence
        + 0.10 * recency
    )


# ── EmbedService ──────────────────────────────────────────────────────────────

class EmbedService:
    """
    Stateless helper — all mutable state lives in the process-wide cache singleton
    and the provider singleton.  Safe to construct once and reuse (MemoryManager
    holds a module-level instance).
    """

    async def embed_text(self, text: str) -> list[float]:
        """Return (cached or freshly computed) embedding for a text string."""
        cached = get_cached(text)
        if cached is not None:
            return cached
        try:
            from app.embeddings.provider import get_provider
            vec = await get_provider().embed(text)
            if vec:
                put_cached(text, vec)
            return vec
        except Exception as exc:
            logger.warning(f"[EMBED] embed_text failed (degraded): {exc}")
            return []

    async def embed_memory(self, key: str, value: Any) -> list[float]:
        """Convert a memory key/value to its canonical text then embed it."""
        return await self.embed_text(memory_to_text(key, value))

    async def embed_memories_batch(
        self,
        memories: list[dict[str, Any]],
        throttle: int = _EMBED_THROTTLE,
    ) -> list[tuple[str, Any, list[float]]]:
        """
        Batch-embed memory dicts.  Returns (key, value, vector) tuples.

        Cache-hit memories are served instantly and do not count against the
        throttle.  Fresh provider calls are capped at `throttle` per invocation
        to bound per-turn latency.  Throttled-out memories return an empty vector
        and will be embedded on a future turn.

        Returns an empty list (not an exception) if the provider is unavailable.
        """
        if not memories:
            return []

        texts   = [memory_to_text(m.get("key", ""), m.get("value")) for m in memories]
        results: list[tuple[str, Any, list[float]]] = []
        fresh_texts: list[str] = []
        fresh_idx:   list[int] = []

        for i, (mem, text) in enumerate(zip(memories, texts)):
            key    = mem.get("key", "")
            cached = get_cached(text)
            if cached is not None:
                results.append((key, mem.get("value"), cached))
            else:
                results.append((key, mem.get("value"), []))
                fresh_texts.append(text)
                fresh_idx.append(i)

        if not fresh_texts:
            log_cache_stats()
            return results

        # Apply per-call throttle
        fresh_texts = fresh_texts[:throttle]
        fresh_idx   = fresh_idx[:throttle]

        try:
            from app.embeddings.provider import get_provider
            vecs = await get_provider().embed_batch(fresh_texts)
            for idx, text, vec in zip(fresh_idx, fresh_texts, vecs):
                if vec:
                    put_cached(text, vec)
                key, val, _ = results[idx]
                results[idx] = (key, val, vec)
            logger.debug(
                f"[EMBED] batch complete | new_vectors={len(fresh_texts)} "
                f"cached_hits={len(results) - len(fresh_texts)}"
            )
        except Exception as exc:
            logger.warning(f"[EMBED] embed_memories_batch provider call failed: {exc}")

        log_cache_stats()
        return results

    def rank_by_query(
        self,
        query_vec: list[float],
        memories: list[dict[str, Any]],
        top_k: int = 8,
    ) -> list[dict[str, Any]]:
        """
        Rank memories by hybrid score against a query embedding.

        Each returned memory is annotated with a 'retrieval_meta' dict:
          {
            source:        "semantic_match" | "structured",
            similarity:    float,      — cosine similarity [0, 1]
            matched_topic: str,        — human-readable topic label
            hybrid_score:  float,      — weighted combination score
          }

        Identity isolation: this method operates on a pre-filtered list already
        scoped to one user — no additional user_id check required here.
        """
        if not query_vec or not memories:
            return []

        scored: list[tuple[float, dict[str, Any]]] = []

        for mem in memories:
            emb = mem.get("embedding", [])
            key = mem.get("key", "")

            if emb and query_vec:
                sim    = cosine_similarity(query_vec, emb)
                score  = hybrid_score(
                    semantic_sim=sim,
                    frequency=mem.get("frequency", 1),
                    confidence=mem.get("confidence", 0.7),
                    updated_at=mem.get("updated_at"),
                )
                source = "semantic_match"
            else:
                sim    = 0.0
                score  = hybrid_score(
                    semantic_sim=0.0,
                    frequency=mem.get("frequency", 1),
                    confidence=mem.get("confidence", 0.7),
                    updated_at=mem.get("updated_at"),
                )
                source = "structured"

            meta = {
                "source":        source,
                "similarity":    round(sim, 4),
                "matched_topic": topic_from_key(key),
                "hybrid_score":  round(score, 4),
            }
            # Shallow copy — don't mutate the original memory dict
            enriched = {**mem, "retrieval_meta": meta}
            scored.append((score, enriched))

        scored.sort(key=lambda t: t[0], reverse=True)
        ranked = [m for _, m in scored[:top_k]]

        if ranked:
            top = ranked[0].get("retrieval_meta", {})
            logger.debug(
                f"[EMBED] rank_by_query | candidates={len(memories)} "
                f"returned={len(ranked)} "
                f"top={top.get('matched_topic')!r} sim={top.get('similarity', 0):.3f}"
            )

        return ranked
