from __future__ import annotations

from app.config import settings
from app.providers.base import BaseChatProvider
from app.providers.http_chat import MockProvider, OpenAICompatibleProvider
from app.schemas.api import ModelConfig, ProviderType


def build_provider(model_cfg: ModelConfig) -> BaseChatProvider:
    if model_cfg.provider == ProviderType.mock:
        return MockProvider()

    if model_cfg.provider == ProviderType.openai:
        api_key = model_cfg.api_key or settings.openai_api_key
        if not api_key:
            raise ValueError("OPENAI_API_KEY missing (or pass model.api_key)")
        return OpenAICompatibleProvider(
            name="openai",
            base_url=(model_cfg.base_url or "https://api.openai.com/v1"),
            api_key=api_key,
            default_headers=model_cfg.headers,
        )

    if model_cfg.provider == ProviderType.openrouter:
        api_key = model_cfg.api_key or settings.openrouter_api_key
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY missing (or pass model.api_key)")
        extra_headers = dict(model_cfg.headers)
        if settings.openrouter_http_referer and "HTTP-Referer" not in extra_headers:
            extra_headers["HTTP-Referer"] = settings.openrouter_http_referer
        if settings.openrouter_app_title and "X-Title" not in extra_headers:
            extra_headers["X-Title"] = settings.openrouter_app_title
        return OpenAICompatibleProvider(
            name="openrouter",
            base_url=(model_cfg.base_url or "https://openrouter.ai/api/v1"),
            api_key=api_key,
            default_headers=extra_headers,
        )

    if model_cfg.provider == ProviderType.openai_compatible:
        if not model_cfg.base_url:
            raise ValueError("model.base_url is required for openai_compatible provider")
        if not model_cfg.api_key:
            raise ValueError("model.api_key is required for openai_compatible provider")
        return OpenAICompatibleProvider(
            name="openai_compatible",
            base_url=model_cfg.base_url,
            api_key=model_cfg.api_key,
            default_headers=model_cfg.headers,
        )

    raise ValueError(f"Unsupported provider: {model_cfg.provider}")

