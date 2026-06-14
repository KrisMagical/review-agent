"""Review coordinator for the Phase 6 multi-agent platform."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents.architecture_agent import ArchitectureAgent
from app.agents.base import BaseAgent
from app.agents.bug_agent import BugAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.knowledge_agent import KnowledgeAgent
from app.agents.quality_agent import QualityAgent
from app.agents.refactor_agent import RefactorAgent
from app.agents.security_agent import SecurityAgent
from app.agents.utils import dedupe_and_sort
from app.models.issue import Issue
from app.project.scanner import ProjectScanner
from magicreview.connected import NetworkPolicy


DEFAULT_AGENT_ORDER = ("knowledge", "quality", "bug", "security", "architecture", "refactor")


def default_agents() -> list[BaseAgent]:
    return [KnowledgeAgent(), QualityAgent(), BugAgent(), SecurityAgent(), ArchitectureAgent(), RefactorAgent()]


class ReviewCoordinator:
    """Build agent context, run agents, and return a stable Issue report."""

    def __init__(self, agents: list[BaseAgent] | None = None, *, scanner: ProjectScanner | None = None) -> None:
        self.agents = agents or default_agents()
        self.scanner = scanner or ProjectScanner()

    def review_project(
        self,
        project_root: str | Path,
        context: AgentContext | None = None,
        *,
        selected_agents: list[str] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        active_context = context or self.build_context(project_root)
        results = self.run_agents(active_context, selected_agents=selected_agents)
        issues = dedupe_and_sort(issue for result in results for issue in result.issues)
        return {"issues": [issue.to_dict() for issue in issues]}

    def build_context(
        self,
        project_root: str | Path,
        *,
        enable_llm: bool = False,
        llm_provider: str | None = None,
        config_path: str | None = None,
        enable_enterprise_rules: bool = True,
        network_policy: NetworkPolicy | None = None,
    ) -> AgentContext:
        root = Path(project_root).resolve()
        return AgentContext(
            project_root=root,
            files=self.scanner.scan(root),
            enable_llm=enable_llm,
            llm_provider=llm_provider,
            config_path=config_path,
            enable_enterprise_rules=enable_enterprise_rules,
            network_policy=network_policy or NetworkPolicy.offline(),
        )

    def run_agents(self, context: AgentContext, *, selected_agents: list[str] | None = None) -> list[AgentResult]:
        requested = self._normalize_selected_agents(selected_agents)
        results: list[AgentResult] = []
        for unknown in [name for name in requested if name not in self.agent_map]:
            results.append(AgentResult(agent_name=unknown, issues=[self._unknown_agent_issue(unknown)]))
        for name in DEFAULT_AGENT_ORDER:
            if name not in requested:
                continue
            agent = self.agent_map.get(name)
            if agent is None:
                continue
            try:
                result = agent.run(context)
            except Exception:
                result = AgentResult(agent_name=name, issues=[self._agent_error_issue(agent.__class__.__name__)], errors=[f"{name} failed"])
            context.static_issues.extend(result.issues)
            context.static_issues = dedupe_and_sort(context.static_issues)
            results.append(result)
        return results

    @property
    def agent_map(self) -> dict[str, BaseAgent]:
        return {agent.name: agent for agent in self.agents}

    @staticmethod
    def _normalize_selected_agents(selected_agents: list[str] | None) -> list[str]:
        if not selected_agents:
            return list(DEFAULT_AGENT_ORDER)
        return [name.strip().lower() for name in selected_agents if name and name.strip()]

    @staticmethod
    def _agent_error_issue(agent_name: str) -> Issue:
        return Issue(
            severity="low",
            type="AgentExecutionError",
            file="<project>",
            line=1,
            message=f"{agent_name} failed during review.",
            suggestion="Check the agent configuration or run with debug mode.",
        )

    @staticmethod
    def _unknown_agent_issue(agent_name: str) -> Issue:
        return Issue(
            severity="low",
            type="UnknownAgent",
            file="<project>",
            line=1,
            message=f"Unknown agent requested: {agent_name}.",
            suggestion="Use one of: quality, bug, architecture, security, knowledge, refactor.",
        )
