from __future__ import annotations

import httpx

from .base import LLMBackend


class OllamaBackend(LLMBackend):
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def generate(self, prompt: str, model: str, timeout: float) -> str:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
            )
            resp.raise_for_status()
            data = resp.json()

        text = str(data.get("response", "")).strip()
        if not text:
            raise ValueError("Ollama returned empty response")
        return text