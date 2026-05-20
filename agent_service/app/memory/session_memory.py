from copy import deepcopy
from typing import Any


class SessionMemory:
    _memory: dict[str, dict[str, Any]] = {}

    @classmethod
    async def get(cls, session_id: str) -> dict[str, Any]:
        return deepcopy(cls._memory.get(session_id, {}))

    @classmethod
    async def update(cls, session_id: str, values: dict[str, Any]) -> dict[str, Any]:
        current = cls._memory.setdefault(session_id, {})
        for key, value in values.items():
            if value not in (None, "", [], {}):
                current[key] = value
        return deepcopy(current)

    @classmethod
    async def clear(cls, session_id: str) -> None:
        cls._memory.pop(session_id, None)
