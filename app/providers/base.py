from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class ChatRequest:
    model: str
    messages: list[dict[str, str]]
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    timeout_seconds: float | None = None


@dataclass
class ChatResponse:
    content: str
    raw: dict[str, Any] | None = None


class BaseChatProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        raise NotImplementedError

