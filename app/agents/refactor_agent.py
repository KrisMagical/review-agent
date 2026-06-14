"""Suggestion-only refactor agent."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import dedupe_and_sort
from app.models.issue import Issue


class RefactorAgent(BaseAgent):
    """Create refactoring recommendations from accumulated review signals."""

    name = "refactor"
    category = "refactor"

    def run(self, context: AgentContext) -> AgentResult:
        issues: list[Issue] = []
        seen: set[tuple[str, str, int]] = set()
        for source_issue in context.static_issues:
            candidate = self._recommendation_for(source_issue)
            if candidate is None:
                continue
            key = (candidate.type, candidate.file, candidate.line)
            if key in seen:
                continue
            seen.add(key)
            issues.append(candidate)
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues))

    @staticmethod
    def _recommendation_for(issue: Issue) -> Issue | None:
        if issue.type in {"GodClass", "GodFile", "LargeModuleResponsibility"}:
            return Issue(
                severity="medium",
                type="SplitModuleSuggestion",
                file=issue.file,
                line=issue.line,
                message="Large component would benefit from responsibility-focused splitting.",
                suggestion="Split the module or class around cohesive business capabilities before making feature changes.",
            )
        if issue.type in {"FunctionTooLongRule", "CyclomaticComplexity", "FastAPIHeavyRouteHandler", "EnterpriseMaxFunctionLength"}:
            suggestion_type = "ExtractServiceSuggestion" if "FastAPI" in issue.type else "ExtractFunctionSuggestion"
            return Issue(
                severity="medium",
                type=suggestion_type,
                file=issue.file,
                line=issue.line,
                message="Complex logic should be extracted into a focused unit.",
                suggestion="Extract cohesive logic into a smaller function or service and keep callers orchestration-only.",
            )
        if issue.type in {"TooManyParametersRule", "EnterpriseMaxParameters"}:
            return Issue(
                severity="low",
                type="IntroduceDTORecommendation",
                file=issue.file,
                line=issue.line,
                message="Parameter list suggests a missing request or configuration object.",
                suggestion="Introduce a DTO or configuration object for related parameters.",
            )
        return None
