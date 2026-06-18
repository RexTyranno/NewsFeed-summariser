from __future__ import annotations

import json
import os
import re
from typing import Any

from .backends import APIBackend, LLMBackend, OllamaBackend


_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", flags=re.MULTILINE)


class LLMError(RuntimeError):
    pass


class LLMClient:
    def __init__(self) -> None:
        backend_name = os.environ.get("LLM_BACKEND", "ollama").strip().lower()
        self.backend_name = backend_name

        if backend_name == "ollama":
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            self.default_model = os.environ.get("OLLAMA_MODEL", "llama3")
            self.backend: LLMBackend = OllamaBackend(base_url=base_url)
        elif backend_name == "api":
            base_url = os.environ.get("API_BASE_URL", "https://api.openai.com/v1")
            api_key = os.environ.get("API_KEY", "").strip()
            self.default_model = os.environ.get("API_MODEL", "gpt-4o-mini")
            if not api_key:
                raise LLMError("API_KEY is required when LLM_BACKEND=api")
            self.backend = APIBackend(base_url=base_url, api_key=api_key)
        else:
            raise LLMError(f"Unsupported LLM_BACKEND: {backend_name}")

    async def generate(
        self,
        prompt: str,
        *,
        model: str | None = None,
        timeout: float = 15.0,
    ) -> str:
        selected_model = (model or self.default_model).strip()
        if not selected_model:
            raise LLMError("No model configured")

        try:
            return await self.backend.generate(prompt=prompt, model=selected_model, timeout=timeout)
        except Exception as exc:
            raise LLMError(str(exc)) from exc

    async def generate_json(
        self,
        prompt: str,
        required_keys: set[str],
        *,
        model: str | None = None,
        timeout: float = 15.0,
    ) -> dict[str, Any] | None:
        try:
            raw = await self.generate(prompt, model=model, timeout=timeout)
        except LLMError:
            return None

        cleaned = _FENCE_RE.sub("", raw).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, dict):
            return None

        if not required_keys.issubset(data.keys()):
            return None

        for key in required_keys:
            if not str(data.get(key, "")).strip():
                return None

        return data


llm_client = LLMClient()