"""
Embedding provider abstraction.

Providers:
  sentence_transformer  — paraphrase-multilingual-MiniLM-L12-v2
                          384-dim, 50+ languages, EN/FR/AR cross-lingual space (default)
  openai                — text-embedding-3-small, 1536-dim, multilingual

Configure via settings.EMBEDDING_PROVIDER ("sentence_transformer" | "openai").

The singleton is created lazily on first call to get_provider() and reused
for the process lifetime. Swapping providers requires a restart.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Minimal async interface for generating float-vector embeddings."""

    DIMENSIONS: int

    async def embed(self, text: str) -> list[float]: ...
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


_instance: "EmbeddingProvider | None" = None


def get_provider() -> EmbeddingProvider:
    """Return (and lazily create) the process-wide embedding provider."""
    global _instance
    if _instance is not None:
        return _instance

    from app.config.settings import settings
    name = (settings.EMBEDDING_PROVIDER or "sentence_transformer").lower()

    if name == "openai":
        from app.embeddings.openai_provider import OpenAIEmbeddingProvider
        _instance = OpenAIEmbeddingProvider()
    else:
        from app.embeddings.sentence_transformer_provider import SentenceTransformerProvider
        _instance = SentenceTransformerProvider()

    return _instance
