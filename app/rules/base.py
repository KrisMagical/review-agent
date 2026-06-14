"""Common rule contracts for magicreview."""

from __future__ import annotations

import ast
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from app.models.issue import Issue, IssueDict, make_issue


@dataclass(frozen=True)
class RuleContext:
    """Source and AST data passed to rules."""

    file_path: str
    source_code: str
    tree: ast.AST | None = None
    changed_lines: set[int] | None = None
    lines: list[str] = field(default_factory=list)


class Rule(ABC):
    """Unified rule interface."""

    name: str
    category: str

    @abstractmethod
    def check(self, context: RuleContext) -> list[Issue]:
        """Return issues detected in the supplied context."""


class BaseRule(Rule):
    """Base class for AST-backed rules with old ``match`` compatibility."""

    name = "BaseRule"
    category = "generic"

    def check(self, context: RuleContext) -> list[Issue]:
        if context.tree is None:
            return []
        issues: list[Issue] = []
        for node in ast.walk(context.tree):
            issues.extend(self.match(node, context.file_path, context.source_code))
        return issues

    def match(self, node: ast.AST, file_path: str, source_code: str) -> list[Issue]:
        return []

    @property
    def rule_id(self) -> str:
        return self.name


__all__ = ["BaseRule", "Issue", "IssueDict", "Rule", "RuleContext", "make_issue"]
