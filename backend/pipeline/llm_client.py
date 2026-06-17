"""Unified async LLM client for OpenRouter, OpenAI, and NVIDIA hosted models."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any, Literal

from openai import AsyncOpenAI

from backend.config.settings import LLMProvider, get_settings
from backend.pipeline.cost_tracker import record_call

CallType = Literal["llm", "vision"]

_PROVIDER_DEFAULTS: dict[LLMProvider, dict[str, str]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "anthropic/claude-3-5-sonnet",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.1-70b-instruct",
    },
}


@dataclass
class LLMResponse:
    content: str
    input_tokens: int
    output_tokens: int
    provider: LLMProvider
    model: str
    cost_usd: float


class LLMClient:
    """Routes chat and vision requests through provider-specific OpenAI-compatible APIs."""

    def __init__(self, provider: LLMProvider | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self.provider: LLMProvider = provider or settings.default_llm_provider
        self.model = model or settings.default_llm_model or _PROVIDER_DEFAULTS[self.provider]["default_model"]
        self._client = self._build_client()

    def _api_key(self) -> str:
        settings = get_settings()
        keys = {
            "openrouter": settings.openrouter_api_key,
            "openai": settings.openai_api_key,
            "nvidia": settings.nvidia_api_key,
        }
        key = keys[self.provider]
        if not key:
            raise ValueError(f"API key not configured for provider: {self.provider}")
        return key

    def _build_client(self) -> AsyncOpenAI:
        base_url = _PROVIDER_DEFAULTS[self.provider]["base_url"]
        default_headers: dict[str, str] | None = None
        if self.provider == "openrouter":
            default_headers = {
                "HTTP-Referer": "https://github.com/meistar-kg",
                "X-Title": "Meistar-KG",
            }
        return AsyncOpenAI(
            api_key=self._api_key(),
            base_url=base_url,
            default_headers=default_headers,
        )

    async def chat(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send a chat completion and record cost."""
        resolved_model = model or self.model
        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0].message
        content = choice.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        record = record_call(
            session_id=session_id,
            call_type="llm",
            provider=self.provider,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider=self.provider,
            model=resolved_model,
            cost_usd=record.cost_usd,
        )

    async def vision(
        self,
        session_id: str,
        image_bytes: bytes,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Extract page content from a PDF page image via a vision-capable model."""
        settings = get_settings()
        resolved_model = model or settings.vision_llm_model
        image_b64 = base64.b64encode(image_bytes).decode("ascii")

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                    },
                ],
            }
        ]

        response = await self._client.chat.completions.create(
            model=resolved_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=max_tokens,
        )

        choice = response.choices[0].message
        content = choice.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        record = record_call(
            session_id=session_id,
            call_type="vision",
            provider=self.provider,
            model=resolved_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            provider=self.provider,
            model=resolved_model,
            cost_usd=record.cost_usd,
        )