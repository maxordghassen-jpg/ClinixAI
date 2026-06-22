import json
import os
from typing import Any

import redis.asyncio as redis
from dotenv import load_dotenv
from app.memory.context_merger import ContextMerger

load_dotenv()


class RedisMemory:
    def __init__(self):
        self.redis = redis.Redis(
            host=os.getenv("REDIS_HOST"),
            port=int(os.getenv("REDIS_PORT")),
            username=os.getenv("REDIS_USERNAME"),
            password=os.getenv("REDIS_PASSWORD"),
            decode_responses=True,
        )

        self.ttl = 1800

    async def get(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        data = await self.redis.get(
            f"{session_id}:memory"
        )

        if not data:
            return {}

        return json.loads(data)

    async def update(
        self,
        session_id: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:

        current = await self.get(session_id)

        current = ContextMerger.merge(
            current,
            values,
        )

        await self.redis.set(
            f"{session_id}:memory",
            json.dumps(current),
            ex=self.ttl,
        )

        return current

    async def clear(
        self,
        session_id: str,
    ) -> None:

        await self.redis.delete(
            f"{session_id}:memory"
        )

    async def delete_keys(
        self,
        session_id: str,
        keys: list[str],
    ):
        current = await self.get(session_id)

        for key in keys:
            current.pop(key, None)

        await self.redis.set(
            f"{session_id}:memory",
            json.dumps(current),
            ex=self.ttl,
        )