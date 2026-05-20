import json
from typing import Any

import httpx

from app.config.settings import settings


class LLMRouter:
    api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not settings.GROQ_API_KEY:
            return {}

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {settings.GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.MODEL_NAME,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()

        content = response.json()["choices"][0]["message"]["content"]
        return json.loads(content)
