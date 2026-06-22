"""
OpenAI embedding provider — text-embedding-3-small

1536 dimensions, multilingual including Arabic and French.
Requires OPENAI_API_KEY in settings.
"""

import logging

logger = logging.getLogger(__name__)

_MODEL_NAME = "text-embedding-3-small"
DIMENSIONS  = 1536


class OpenAIEmbeddingProvider:

    DIMENSIONS = DIMENSIONS

    def __init__(self) -> None:
        from app.config.settings import settings
        if not settings.OPENAI_API_KEY:
            raise RuntimeError(
                "EMBEDDING_PROVIDER=openai but OPENAI_API_KEY is not set"
            )
        from openai import AsyncOpenAI  # type: ignore
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info(f"[EMBED] OpenAI provider initialised: {_MODEL_NAME} ({DIMENSIONS}-dim)")

    async def embed(self, text: str) -> list[float]:
        resp = await self._client.embeddings.create(model=_MODEL_NAME, input=text)
        return resp.data[0].embedding

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        resp = await self._client.embeddings.create(model=_MODEL_NAME, input=texts)
        return [d.embedding for d in resp.data]
