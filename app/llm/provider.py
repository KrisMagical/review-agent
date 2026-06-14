"""LLM provider abstraction for architecture review."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from typing import Any

import httpx

from magicreview.connected import NetworkPolicy
from magicreview.config.env import get_env


class LLMProviderError(RuntimeError):
    """Raised when an LLM provider is unavailable or fails."""


class LLMProvider(ABC):
    name = "base"
    requires_network = False

    @abstractmethod
    def complete(self, prompt: str, policy: NetworkPolicy | None = None) -> str:
        """Return raw model text for a prompt."""


class NoneLLMProvider(LLMProvider):
    name = "none"
    requires_network = False

    def complete(self, prompt: str, policy: NetworkPolicy | None = None) -> str:
        raise LLMProviderError("LLM architecture review is not configured.")


class OpenAILLMProvider(LLMProvider):
    name = "openai"
    requires_network = True

    def __init__(self, model: str | None = None, *, timeout: float = 30, max_output_tokens: int = 1200) -> None:
        self.model = model or get_env("LLM_MODEL") or "gpt-4o-mini"
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens

    def complete(self, prompt: str, policy: NetworkPolicy | None = None) -> str:
        self._check_policy(policy)
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMProviderError("openai package is not installed.") from exc
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=self.max_output_tokens,
        )
        return response.choices[0].message.content or ""

    def _check_policy(self, policy: NetworkPolicy | None) -> None:
        active = policy or NetworkPolicy.offline()
        if not active.allows_provider(self.name):
            raise LLMProviderError("Network LLM provider is not allowed by MagicReview NetworkPolicy.")


class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"
    requires_network = True

    def __init__(self, model: str | None = None, *, timeout: float = 30, max_output_tokens: int = 1200, http_client: httpx.Client | None = None) -> None:
        self.model = model or get_env("ANTHROPIC_MODEL") or "claude-3-5-sonnet-latest"
        self.timeout = timeout
        self.max_output_tokens = max_output_tokens
        self.http_client = http_client

    def complete(self, prompt: str, policy: NetworkPolicy | None = None) -> str:
        active = policy or NetworkPolicy.offline()
        if not active.allows_provider(self.name):
            raise LLMProviderError("Network LLM provider is not allowed by MagicReview NetworkPolicy.")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured.")
        client = self.http_client or httpx.Client(timeout=self.timeout)
        response = client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": self.model,
                "max_tokens": self.max_output_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        if response.status_code >= 400:
            raise LLMProviderError(f"Anthropic API request failed with status {response.status_code}.")
        payload = response.json()
        content = payload.get("content", [])
        if content and isinstance(content, list):
            first = content[0]
            if isinstance(first, dict):
                return str(first.get("text", ""))
        return ""


class AzureOpenAILLMProvider(OpenAILLMProvider):
    name = "azure_openai"

    def complete(self, prompt: str, policy: NetworkPolicy | None = None) -> str:
        raise LLMProviderError("Azure OpenAI provider is not configured in this lightweight build.")


def provider_from_env(name: str | None = None) -> LLMProvider:
    provider = (name or get_env("LLM_PROVIDER") or "none").lower()
    if provider == "openai":
        return OpenAILLMProvider()
    if provider == "anthropic":
        return AnthropicLLMProvider()
    if provider in {"azure", "azure_openai", "azure-openai"}:
        return AzureOpenAILLMProvider()
    if provider == "mock":
        from app.llm.mock_provider import MockLLMProvider

        return MockLLMProvider()
    return NoneLLMProvider()
