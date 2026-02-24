from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

import httpx

from app.providers.base import BaseChatProvider, ChatRequest, ChatResponse


class OpenAICompatibleProvider(BaseChatProvider):
    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_key: str,
        default_headers: Optional[dict[str, str]] = None,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.default_headers = default_headers or {}
        self._client = client

    async def chat(self, req: ChatRequest) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": req.model,
            "messages": req.messages,
        }
        if req.temperature is not None:
            payload["temperature"] = req.temperature
        if req.max_tokens is not None:
            payload["max_tokens"] = req.max_tokens
        if req.top_p is not None:
            payload["top_p"] = req.top_p

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            **self.default_headers,
        }

        client = self._client or httpx.AsyncClient(timeout=req.timeout_seconds or 120.0)
        owns_client = self._client is None
        try:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = self._extract_content(data)
            return ChatResponse(content=content, raw=data)
        finally:
            if owns_client:
                await client.aclose()

    @staticmethod
    def _extract_content(data: dict[str, Any]) -> str:
        try:
            choice = data["choices"][0]
            message = choice["message"]
            content = message["content"]
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                # Some providers return multimodal chunks.
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        txt = item.get("text")
                        if txt:
                            parts.append(str(txt))
                return "\n".join(parts).strip()
            return str(content)
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise ValueError(f"Unexpected response payload: {json.dumps(data)[:500]}") from exc


class MockProvider(BaseChatProvider):
    name = "mock"

    async def chat(self, req: ChatRequest) -> ChatResponse:
        await asyncio.sleep(0.01)
        user_content = "\n".join(m["content"] for m in req.messages if m.get("role") == "user")
        if "JSON" in user_content.upper():
            content = json.dumps(
                {
                    "summary": user_content[:80],
                    "length": len(user_content),
                    "model": req.model,
                },
                ensure_ascii=False,
            )
        else:
            content = f"[{req.model}] {user_content[:200]}"
        return ChatResponse(content=content, raw={"mock": True})
