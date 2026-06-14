"""Network access policy for connected magicreview services."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from magicreview.config.env import env_bool, get_env


CodeSharingMode = Literal["none", "summary_only", "snippets", "full_context"]


@dataclass(frozen=True)
class NetworkPolicy:
    """Explicit consent gate for networked providers and hosted services."""

    enabled: bool = False
    allow_llm: bool = False
    allow_github_api: bool = False
    allow_remote_mcp: bool = False
    code_sharing_mode: CodeSharingMode = "none"
    allowed_providers: list[str] = field(default_factory=list)
    require_explicit_consent: bool = True
    audit_enabled: bool = True

    @classmethod
    def offline(cls) -> "NetworkPolicy":
        return cls()

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "NetworkPolicy":
        if not data:
            return cls.offline()
        mode = str(data.get("code_sharing_mode", data.get("codeSharingMode", "none"))).replace("-", "_")
        if mode not in {"none", "summary_only", "snippets", "full_context"}:
            mode = "none"
        providers = data.get("allowed_providers") or data.get("allowedProviders") or []
        if isinstance(providers, str):
            providers = [item.strip() for item in providers.split(",") if item.strip()]
        return cls(
            enabled=bool(data.get("enabled", False)),
            allow_llm=bool(data.get("allow_llm", data.get("allowLlm", False))),
            allow_github_api=bool(data.get("allow_github_api", data.get("allowGithubApi", False))),
            allow_remote_mcp=bool(data.get("allow_remote_mcp", data.get("allowRemoteMcp", False))),
            code_sharing_mode=mode,  # type: ignore[arg-type]
            allowed_providers=list(providers) if isinstance(providers, list) else [],
            require_explicit_consent=bool(data.get("require_explicit_consent", data.get("requireExplicitConsent", True))),
            audit_enabled=bool(data.get("audit_enabled", data.get("auditEnabled", True))),
        )

    @classmethod
    def from_env(cls) -> "NetworkPolicy":
        return cls(
            enabled=env_bool("NETWORK_ENABLED", False),
            allow_llm=env_bool("ALLOW_LLM", False),
            allow_github_api=env_bool("ALLOW_GITHUB_API", False),
            allow_remote_mcp=env_bool("ALLOW_REMOTE_MCP", False),
            code_sharing_mode=_mode(get_env("CODE_SHARING_MODE", "none") or "none"),
            allowed_providers=[item.strip() for item in (get_env("ALLOWED_PROVIDERS", "") or "").split(",") if item.strip()],
            require_explicit_consent=env_bool("REQUIRE_EXPLICIT_CONSENT", True),
            audit_enabled=env_bool("AUDIT_NETWORK", True),
        )

    def allows_provider(self, provider: str, *, needs_llm: bool = True) -> bool:
        if not self.enabled:
            return False
        if needs_llm and not self.allow_llm:
            return False
        if self.code_sharing_mode == "none":
            return False
        if self.allowed_providers and provider not in self.allowed_providers:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "allow_llm": self.allow_llm,
            "allow_github_api": self.allow_github_api,
            "allow_remote_mcp": self.allow_remote_mcp,
            "code_sharing_mode": self.code_sharing_mode,
            "allowed_providers": list(self.allowed_providers),
            "require_explicit_consent": self.require_explicit_consent,
            "audit_enabled": self.audit_enabled,
        }


def _mode(value: str) -> CodeSharingMode:
    normalized = value.replace("-", "_")
    if normalized in {"summary_only", "snippets", "full_context"}:
        return normalized  # type: ignore[return-value]
    return "none"
