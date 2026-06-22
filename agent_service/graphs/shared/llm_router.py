import json
from typing import Any

import openai

from app.config.settings import settings


class LLMRouter:
    async def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if not settings.OPENAI_API_KEY:
            return {}

        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.MODEL_NAME,
            max_tokens=512,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return json.loads(content)
