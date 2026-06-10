"""Model provider settings for the Dashboard."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from reviewagent.connected import NetworkPolicy
from reviewagent.storage.database import connect, init_db


PROVIDERS = {
    "none",
    "mock",
    "openai",
    "anthropic",
    "azure_openai",
    "openai_compatible",
    "ollama",
    "enterprise_gateway",
}
CODE_SHARING_MODES = {"none", "summary_only", "snippets", "full_context"}
ENV_KEY_BY_PROVIDER = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "azure_openai": "AZURE_OPENAI_API_KEY",
    "openai_compatible": "REVIEWAGENT_OPENAI_COMPATIBLE_API_KEY",
    "enterprise_gateway": "REVIEWAGENT_ENTERPRISE_LLM_API_KEY",
}


@dataclass
class ModelProviderSettings:
    provider: str = "none"
    enabled: bool = False
    model: str = ""
    base_url: str = ""
    api_key_value: str = ""
    api_key_source: str = "none"
    timeout_seconds: int = 30
    max_context_chars: int = 60000
    code_sharing_mode: str = "none"
    allow_network: bool = False
    allow_llm: bool = False
    audit_enabled: bool = True
    organization: str = ""
    azure_endpoint: str = ""
    azure_deployment: str = ""
    azure_api_version: str = ""

    def network_policy(self) -> NetworkPolicy:
        if self.provider == "none" or not self.enabled:
            return NetworkPolicy.offline()
        if self.provider == "mock":
            return NetworkPolicy(audit_enabled=self.audit_enabled)
        return NetworkPolicy(
            enabled=self.allow_network,
            allow_llm=self.allow_llm,
            code_sharing_mode=self.code_sharing_mode,  # type: ignore[arg-type]
            allowed_providers=[self.provider],
            audit_enabled=self.audit_enabled,
        )

    def to_safe_dict(self) -> dict[str, Any]:
        effective_key = self.effective_api_key()
        return {
            "provider": self.provider,
            "enabled": self.enabled,
            "model": self.model,
            "base_url": self.base_url or None,
            "api_key_source": self.effective_api_key_source(),
            "api_key_masked": mask_api_key(effective_key),
            "timeout_seconds": self.timeout_seconds,
            "max_context_chars": self.max_context_chars,
            "code_sharing_mode": self.code_sharing_mode,
            "allow_network": self.allow_network,
            "allow_llm": self.allow_llm,
            "audit_enabled": self.audit_enabled,
            "organization": self.organization or None,
            "azure_endpoint": self.azure_endpoint or None,
            "azure_deployment": self.azure_deployment or None,
            "azure_api_version": self.azure_api_version or None,
        }

    def effective_api_key(self) -> str:
        env_name = ENV_KEY_BY_PROVIDER.get(self.provider)
        if env_name and os.getenv(env_name):
            return os.getenv(env_name, "")
        return self.api_key_value

    def effective_api_key_source(self) -> str:
        env_name = ENV_KEY_BY_PROVIDER.get(self.provider)
        if env_name and os.getenv(env_name):
            return "env"
        if self.api_key_value:
            return "stored"
        return "none"


class ModelSettingsRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        init_db(db_path)

    def get(self) -> ModelProviderSettings:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM model_provider_settings WHERE id = 1").fetchone()
        if row is None:
            return settings_from_env(ModelProviderSettings())
        return settings_from_env(
            ModelProviderSettings(
                provider=row["provider"],
                enabled=bool(row["enabled"]),
                model=row["model"] or "",
                base_url=row["base_url"] or "",
                api_key_value=row["api_key_value"] or "",
                api_key_source=row["api_key_source"] or "none",
                timeout_seconds=int(row["timeout_seconds"]),
                max_context_chars=int(row["max_context_chars"]),
                code_sharing_mode=row["code_sharing_mode"],
                allow_network=bool(row["allow_network"]),
                allow_llm=bool(row["allow_llm"]),
                audit_enabled=bool(row["audit_enabled"]),
                organization=row["organization"] or "",
                azure_endpoint=row["azure_endpoint"] or "",
                azure_deployment=row["azure_deployment"] or "",
                azure_api_version=row["azure_api_version"] or "",
            )
        )

    def save(self, data: dict[str, Any]) -> ModelProviderSettings:
        current = self.get()
        provider = _provider(data.get("provider", current.provider))
        mode = _sharing_mode(data.get("code_sharing_mode", current.code_sharing_mode))
        api_key = str(data.get("api_key", "") or "")
        keep_existing_key = not api_key
        stored_key = current.api_key_value if keep_existing_key else api_key
        settings = ModelProviderSettings(
            provider=provider,
            enabled=_bool_value(data.get("enabled", provider not in {"none"})),
            model=str(data.get("model", current.model) or ""),
            base_url=str(data.get("base_url", current.base_url) or ""),
            api_key_value=stored_key,
            api_key_source="stored" if stored_key else "none",
            timeout_seconds=_int_value(data.get("timeout_seconds", current.timeout_seconds), 30),
            max_context_chars=_int_value(data.get("max_context_chars", current.max_context_chars), 60000),
            code_sharing_mode=mode,
            allow_network=_bool_value(data.get("allow_network", current.allow_network)),
            allow_llm=_bool_value(data.get("allow_llm", current.allow_llm)),
            audit_enabled=_bool_value(data.get("audit_enabled", current.audit_enabled), default=True),
            organization=str(data.get("organization", current.organization) or ""),
            azure_endpoint=str(data.get("azure_endpoint", current.azure_endpoint) or ""),
            azure_deployment=str(data.get("azure_deployment", current.azure_deployment) or ""),
            azure_api_version=str(data.get("azure_api_version", current.azure_api_version) or ""),
        )
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO model_provider_settings(
                    id, provider, enabled, model, base_url, api_key_value, api_key_source,
                    timeout_seconds, max_context_chars, code_sharing_mode, allow_network, allow_llm,
                    audit_enabled, organization, azure_endpoint, azure_deployment, azure_api_version
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    provider=excluded.provider,
                    enabled=excluded.enabled,
                    model=excluded.model,
                    base_url=excluded.base_url,
                    api_key_value=excluded.api_key_value,
                    api_key_source=excluded.api_key_source,
                    timeout_seconds=excluded.timeout_seconds,
                    max_context_chars=excluded.max_context_chars,
                    code_sharing_mode=excluded.code_sharing_mode,
                    allow_network=excluded.allow_network,
                    allow_llm=excluded.allow_llm,
                    audit_enabled=excluded.audit_enabled,
                    organization=excluded.organization,
                    azure_endpoint=excluded.azure_endpoint,
                    azure_deployment=excluded.azure_deployment,
                    azure_api_version=excluded.azure_api_version,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (
                    settings.provider,
                    int(settings.enabled),
                    settings.model,
                    settings.base_url,
                    settings.api_key_value,
                    settings.api_key_source,
                    settings.timeout_seconds,
                    settings.max_context_chars,
                    settings.code_sharing_mode,
                    int(settings.allow_network),
                    int(settings.allow_llm),
                    int(settings.audit_enabled),
                    settings.organization,
                    settings.azure_endpoint,
                    settings.azure_deployment,
                    settings.azure_api_version,
                ),
            )
        return self.get()

    def clear_api_key(self) -> ModelProviderSettings:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO model_provider_settings(id, provider)
                VALUES (1, 'none')
                ON CONFLICT(id) DO UPDATE SET
                    api_key_value='',
                    api_key_source='none',
                    updated_at=CURRENT_TIMESTAMP
                """
            )
        return self.get()


class ModelProviderTester:
    def __init__(self, http_client: httpx.Client | None = None) -> None:
        self.http_client = http_client

    def test(self, settings: ModelProviderSettings) -> dict[str, Any]:
        provider = settings.provider
        if provider == "none" or not settings.enabled:
            return {"ok": False, "message": "Provider is disabled."}
        if provider == "mock":
            return {"ok": True, "message": "Mock provider replied OK."}
        policy = settings.network_policy()
        if not policy.allows_provider(provider):
            return {"ok": False, "message": "Network LLM provider is not allowed by current NetworkPolicy."}
        if not settings.effective_api_key() and provider not in {"ollama"}:
            return {"ok": False, "message": "API key is not configured."}
        try:
            return self._test_network_provider(settings)
        except Exception:
            return {"ok": False, "message": "Provider test failed."}

    def _test_network_provider(self, settings: ModelProviderSettings) -> dict[str, Any]:
        client = self.http_client or httpx.Client(timeout=settings.timeout_seconds)
        if settings.provider == "ollama":
            base_url = settings.base_url or os.getenv("REVIEWAGENT_OLLAMA_BASE_URL") or "http://localhost:11434"
            response = client.get(f"{base_url.rstrip('/')}/api/tags")
            return {"ok": response.status_code < 400, "message": "Ollama connection test completed."}
        if settings.provider == "anthropic":
            response = client.post(
                "https://api.anthropic.com/v1/messages",
                headers={"x-api-key": settings.effective_api_key(), "anthropic-version": "2023-06-01"},
                json={"model": settings.model, "max_tokens": 5, "messages": [{"role": "user", "content": "Reply with OK."}]},
            )
            return {"ok": response.status_code < 400, "message": "Anthropic connection test completed."}
        url = _completion_url(settings)
        response = client.post(
            url,
            headers={"Authorization": f"Bearer {settings.effective_api_key()}"},
            json={"model": settings.model, "messages": [{"role": "user", "content": "Reply with OK."}], "max_tokens": 5},
        )
        return {"ok": response.status_code < 400, "message": "Provider connection test completed."}


def settings_from_env(settings: ModelProviderSettings) -> ModelProviderSettings:
    provider = os.getenv("REVIEWAGENT_LLM_PROVIDER")
    if provider:
        env_provider = _provider(provider)
        if env_provider != "none" or settings.provider == "none":
            settings.provider = env_provider
            settings.enabled = settings.provider not in {"none"}
    settings.model = os.getenv("REVIEWAGENT_LLM_MODEL") or settings.model
    settings.base_url = (
        os.getenv("REVIEWAGENT_OPENAI_COMPATIBLE_BASE_URL")
        or os.getenv("REVIEWAGENT_OLLAMA_BASE_URL")
        or os.getenv("REVIEWAGENT_ENTERPRISE_LLM_BASE_URL")
        or settings.base_url
    )
    settings.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT") or settings.azure_endpoint
    settings.azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT") or settings.azure_deployment
    settings.azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION") or settings.azure_api_version
    return settings


def mask_api_key(value: str) -> str | None:
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"sk-****{value[-4:]}" if value.startswith("sk-") else f"****{value[-4:]}"


def _provider(value: Any) -> str:
    normalized = str(value or "none").strip().lower().replace("-", "_")
    return normalized if normalized in PROVIDERS else "none"


def _sharing_mode(value: Any) -> str:
    normalized = str(value or "none").strip().lower().replace("-", "_")
    return normalized if normalized in CODE_SHARING_MODES else "none"


def _bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _completion_url(settings: ModelProviderSettings) -> str:
    if settings.provider == "openai":
        return f"{(settings.base_url or 'https://api.openai.com/v1').rstrip('/')}/chat/completions"
    if settings.provider == "azure_openai":
        endpoint = settings.azure_endpoint.rstrip("/")
        deployment = settings.azure_deployment
        version = settings.azure_api_version or "2024-02-15-preview"
        return f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={version}"
    if settings.provider == "enterprise_gateway":
        return f"{(settings.base_url or os.getenv('REVIEWAGENT_ENTERPRISE_LLM_BASE_URL', '')).rstrip('/')}/chat/completions"
    return f"{settings.base_url.rstrip('/')}/chat/completions"
