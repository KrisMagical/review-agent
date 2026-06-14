"""Shared context objects for the Phase 6 multi-agent review platform."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.enterprise import EnterpriseRuleConfig
from app.models.issue import Issue
from magicreview.connected import NetworkPolicy


@dataclass
class AgentContext:
    """Data shared by review agents during one project review."""

    project_root: Path
    files: list[Path] = field(default_factory=list)
    diff: str | None = None
    static_issues: list[Issue] = field(default_factory=list)
    architecture_context: Any | None = None
    enterprise_config: EnterpriseRuleConfig | None = None
    dependency_graph_summary: dict[str, Any] = field(default_factory=dict)
    fastapi_summary: dict[str, Any] = field(default_factory=dict)
    llm_provider: str | None = None
    enable_llm: bool = False
    config_path: str | None = None
    enable_enterprise_rules: bool = True
    network_policy: NetworkPolicy = field(default_factory=NetworkPolicy.offline)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result returned by an individual review agent."""

    agent_name: str
    issues: list[Issue] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "issues": [issue.to_dict() for issue in self.issues],
            "notes": list(self.notes),
            "metrics": dict(self.metrics),
            "errors": list(self.errors),
        }
