from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ChatRequest:
    model: str
    messages: list[dict[str, str]]
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    top_p: Optional[float] = None
    timeout_seconds: Optional[float] = None


@dataclass
class ChatResponse:
    content: str
    raw: Optional[dict[str, Any]] = None


class BaseChatProvider(ABC):
    name: str

    @abstractmethod
    async def chat(self, req: ChatRequest) -> ChatResponse:
        raise NotImplementedError
