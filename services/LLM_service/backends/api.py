from __future__ import annotations

import httpx

from .base import LLMBackend


class APIBackend(LLMBackend):
    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def _chat_url(self) -> str:
        if self.base_url.endswith("/v1"):
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    async def generate(self, prompt: str, model: str, timeout: float) -> str:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }

        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(self._chat_url(), headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        choices = data.get("choices") or []
        if not choices:
            raise ValueError("API backend returned no choices")
        content = choices[0].get("message", {}).get("content", "")
        text = str(content).strip()
        if not text:
            raise ValueError("API backend returned empty content")
        return text