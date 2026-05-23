"""
Shared async HTTP transport.

Single implementation of GET / POST / DELETE used by all service clients.
Replaces the identical MCPClient classes that lived in both
graphs/patient/mcp/client.py and graphs/doctor/mcp/client.py.
"""
from __future__ import annotations

from typing import Any

import httpx

_DEFAULT_TIMEOUT = 15


class BaseClient:
    """
    Thin async HTTP wrapper.  All methods raise on non-2xx responses
    (httpx raises_for_status) and return the parsed JSON body.
    """

    def __init__(self, timeout: int = _DEFAULT_TIMEOUT) -> None:
        self._timeout = timeout

    async def get(
        self,
        base_url: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{base_url}{path}", params=params)
        response.raise_for_status()
        return response.json()

    async def post(
        self,
        base_url: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{base_url}{path}", json=payload or {})
        response.raise_for_status()
        return response.json()

    async def delete(
        self,
        base_url: str,
        path: str,
    ) -> Any:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.delete(f"{base_url}{path}")
        response.raise_for_status()
        return response.json()
