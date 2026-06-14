"""Enterprise policy and project knowledge review agent."""

from __future__ import annotations

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import dedupe_and_sort
from app.enterprise import EnterpriseRuleEngine, RuleConfigLoader


class KnowledgeAgent(BaseAgent):
    """Load and execute configured enterprise policy rules."""

    name = "knowledge"
    category = "knowledge"

    def __init__(self, config_loader: RuleConfigLoader | None = None) -> None:
        self.config_loader = config_loader or RuleConfigLoader()

    def run(self, context: AgentContext) -> AgentResult:
        if not context.enable_enterprise_rules:
            return AgentResult(agent_name=self.name)
        config = context.enterprise_config or self.config_loader.load(context.project_root, context.config_path)
        context.enterprise_config = config
        issues = list(config.errors)
        if config.has_rules:
            issues.extend(EnterpriseRuleEngine(config).run_project(context.project_root, context.files))
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues), metrics={"rules_enabled": len(config.rules)})
