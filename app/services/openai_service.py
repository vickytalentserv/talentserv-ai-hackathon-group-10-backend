from __future__ import annotations

import json
import re

import httpx

from app.config import settings


class OpenAIService:
    def is_enabled(self) -> bool:
        return bool(settings.openai_api_key and settings.openai_enabled)

    def chat_json(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.0,
    ) -> dict | list | None:
        if not self.is_enabled():
            return None

        try:
            response = httpx.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "temperature": temperature,
                    "response_format": {"type": "json_object"},
                },
                timeout=settings.openai_timeout_seconds,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return parse_json_content(content)
        except Exception:
            return None


def parse_json_content(content: str) -> dict | list | None:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None
