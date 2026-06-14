"""Bug-risk review agent."""

from __future__ import annotations

import ast

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import call_name, dedupe_and_sort, parse_python, read_python_source
from app.models.issue import Issue
from app.rules.bug import FileLeakRule, IndexRiskRule, KeyErrorRule, NoneRiskRule, ZeroDivisionRule
from app.rules.engine import RuleEngine


class BugAgent(BaseAgent):
    """Run runtime-risk rules and a few lightweight bug heuristics."""

    name = "bug"
    category = "bug"

    def run(self, context: AgentContext) -> AgentResult:
        rule_engine = RuleEngine([NoneRiskRule(), IndexRiskRule(), KeyErrorRule(), ZeroDivisionRule(), FileLeakRule()])
        issues: list[Issue] = []
        for relative_path in context.files:
            file_path = relative_path.as_posix()
            source = read_python_source(context.project_root, relative_path)
            if source is None:
                continue
            issues.extend(rule_engine.review_source(file_path=file_path, source_code=source))
            tree = parse_python(file_path, source)
            if tree is not None:
                issues.extend(self._extra_bug_issues(file_path, tree))
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues))

    def _extra_bug_issues(self, file_path: str, tree: ast.AST) -> list[Issue]:
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for default in [*node.args.defaults, *node.args.kw_defaults]:
                    if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                        issues.append(
                            Issue(
                                severity="medium",
                                type="MutableDefaultArgumentRisk",
                                file=file_path,
                                line=getattr(node, "lineno", 1),
                                message="Function uses a mutable default argument.",
                                suggestion="Use None as the default and create the mutable value inside the function.",
                            )
                        )
            elif isinstance(node, ast.ExceptHandler) and node.type is None:
                issues.append(
                    Issue(
                        severity="low",
                        type="BroadExceptionRisk",
                        file=file_path,
                        line=getattr(node, "lineno", 1),
                        message="Bare except catches all exceptions.",
                        suggestion="Catch specific exception types and handle only expected failures.",
                    )
                )
            elif isinstance(node, ast.Call) and call_name(node.func) in {"pickle.loads", "yaml.load"}:
                issues.append(
                    Issue(
                        severity="high",
                        type="UnsafeDeserializationRisk",
                        file=file_path,
                        line=getattr(node, "lineno", 1),
                        message="Unsafe deserialization call detected.",
                        suggestion="Use safe loaders and avoid deserializing untrusted input.",
                    )
                )
        return issues
