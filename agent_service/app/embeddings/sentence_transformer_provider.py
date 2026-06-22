"""
SentenceTransformer provider — paraphrase-multilingual-MiniLM-L12-v2

Why this model:
  - 384 dimensions (compact, fast cosine similarity)
  - Trained on 50+ languages including English, French, Arabic
  - Cross-lingual semantic space: "cardiologist" ≈ "cardiologue" ≈ "طبيب القلب"
  - ~120ms cold-start inference, ~2ms warm, 278 MB on disk

Model is loaded once at first use and kept alive for the process lifetime.
All inference runs in a thread-pool executor to avoid blocking the async loop.
normalize_embeddings=True ensures dot product == cosine similarity.
"""

import asyncio
import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

_MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS  = 384


@lru_cache(maxsize=1)
def _load_model():
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
        model = SentenceTransformer(_MODEL_NAME)
        logger.info(f"[EMBED] sentence-transformer loaded: {_MODEL_NAME} ({DIMENSIONS}-dim)")
        return model
    except ImportError:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Run: pip install sentence-transformers"
        )


def check_available() -> tuple[bool, str]:
    """
    Return (is_available, detail) without raising.
    Safe to call at startup as a health probe.
    """
    try:
        _load_model()
        return True, f"model={_MODEL_NAME} dimensions={DIMENSIONS}"
    except Exception as exc:
        return False, str(exc)


class SentenceTransformerProvider:

    DIMENSIONS = DIMENSIONS

    async def embed(self, text: str) -> list[float]:
        loop  = asyncio.get_event_loop()
        model = _load_model()
        return await loop.run_in_executor(
            None,
            lambda: model.encode(text, normalize_embeddings=True).tolist(),
        )

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        loop  = asyncio.get_event_loop()
        model = _load_model()
        return await loop.run_in_executor(
            None,
            lambda: model.encode(texts, normalize_embeddings=True).tolist(),
        )
