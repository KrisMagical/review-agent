"""Architecture-focused review agent."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import dedupe_and_sort
from app.analyzers.dependency_analyzer import DependencyAnalyzer
from app.analyzers.fastapi import FastAPIProjectAnalyzer
from app.architecture import ArchitectureReviewer
from app.llm.provider import provider_from_env
from app.rules.architecture import GodObjectDetector


class ArchitectureAgent(BaseAgent):
    """Run import graph, God Object, FastAPI architecture, and optional LLM review."""

    name = "architecture"
    category = "architecture"

    def run(self, context: AgentContext) -> AgentResult:
        issues = []
        dependency_analyzer = DependencyAnalyzer(context.project_root)
        graph = dependency_analyzer.build_graph()
        issues.extend(dependency_analyzer.detect_cycles(graph))
        issues.extend(dependency_analyzer.detect_high_coupling(graph))
        issues.extend(GodObjectDetector(context.project_root).analyze_project(graph=graph))
        issues.extend(FastAPIProjectAnalyzer().analyze_project(context.project_root))
        if context.enable_llm:
            reviewer = ArchitectureReviewer(
                provider=provider_from_env(context.llm_provider),
                network_policy=context.network_policy,
                audit_source="cli",
                project_name=context.project_root.name,
                target_ref=str(context.project_root),
            )
            issues.extend(reviewer.review_project(context.project_root, static_issues=[*context.static_issues, *issues]))
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues))
