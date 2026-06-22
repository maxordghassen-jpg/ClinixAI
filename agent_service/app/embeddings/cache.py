"""
Embedding cache — SHA-256-keyed LRU dict, process-scoped.

Avoids re-embedding identical memory texts across turns. Embeddings for the
same model are deterministic, so the cache is valid until the provider changes
or the process restarts.

Thread-safe for asyncio workloads (single event loop, no concurrent writes).
Cache statistics (hits, misses, hit rate) are tracked for observability.
"""

import hashlib
import logging
from collections import OrderedDict
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_MAX_SIZE = 2000  # ~2 000 × 384 floats × 4 bytes ≈ 3 MB


class EmbeddingCache:

    def __init__(self, max_size: int = _DEFAULT_MAX_SIZE) -> None:
        self._store:  OrderedDict[str, list[float]] = OrderedDict()
        self._max    = max_size
        self._hits   = 0
        self._misses = 0

    @staticmethod
    def _key(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]

    def get(self, text: str) -> Optional[list[float]]:
        k = self._key(text)
        if k in self._store:
            self._store.move_to_end(k)
            self._hits += 1
            return self._store[k]
        self._misses += 1
        return None

    def put(self, text: str, vector: list[float]) -> None:
        k = self._key(text)
        if k in self._store:
            self._store.move_to_end(k)
        else:
            if len(self._store) >= self._max:
                self._store.popitem(last=False)  # evict LRU
        self._store[k] = vector

    # ── Observability ─────────────────────────────────────────────────────────

    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    def stats(self) -> dict:
        return {
            "size":     len(self._store),
            "max":      self._max,
            "hits":     self._hits,
            "misses":   self._misses,
            "hit_rate": round(self.hit_rate(), 3),
        }

    def __len__(self) -> int:
        return len(self._store)


# ── Process-wide singleton ────────────────────────────────────────────────────

_cache = EmbeddingCache()


def get_cached(text: str) -> Optional[list[float]]:
    return _cache.get(text)


def put_cached(text: str, vector: list[float]) -> None:
    _cache.put(text, vector)


def cache_stats() -> dict:
    return _cache.stats()


def log_cache_stats() -> None:
    s = _cache.stats()
    logger.debug(
        f"[EMBED CACHE] size={s['size']}/{s['max']} "
        f"hits={s['hits']} misses={s['misses']} rate={s['hit_rate']:.1%}"
    )
