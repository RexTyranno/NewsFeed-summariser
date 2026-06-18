from __future__ import annotations

from abc import ABC, abstractmethod


class LLMBackend(ABC):
    @abstractmethod
    async def generate(self, prompt: str, model: str, timeout: float) -> str:
        """Return raw model text for the prompt."""