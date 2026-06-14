"""Quality-focused review agent."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import dedupe_and_sort, read_python_source
from app.analyzers.complexity_analyzer import RadonAdapter
from app.analyzers.ruff_adapter import RuffAdapter
from app.rules.engine import RuleEngine
from app.rules.quality import FunctionTooLongRule, MagicNumberRule, TooManyParametersRule, TypeHintRule


class QualityAgent(BaseAgent):
    """Run quality, style, and complexity checks."""

    name = "quality"
    category = "quality"

    def run(self, context: AgentContext) -> AgentResult:
        rule_engine = RuleEngine([FunctionTooLongRule(), TooManyParametersRule(), TypeHintRule(), MagicNumberRule()])
        issues = []
        for relative_path in context.files:
            source = read_python_source(context.project_root, relative_path)
            if source is None:
                continue
            issues.extend(rule_engine.review_source(file_path=relative_path.as_posix(), source_code=source))
        issues.extend(RuffAdapter(workspace_root=context.project_root).check_project(context.project_root))
        issues.extend(RadonAdapter(workspace_root=context.project_root).analyze_project(context.project_root))
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues))
