"""Security-focused review agent."""

from __future__ import annotations

import ast
import re

from app.agents.base import BaseAgent
from app.agents.context import AgentContext, AgentResult
from app.agents.utils import call_name, dedupe_and_sort, parse_python, read_python_source
from app.models.issue import Issue
from app.rules.bug import PathTraversalRule, SQLInjectionRule
from app.rules.engine import RuleEngine


class SecurityAgent(BaseAgent):
    """Run security rules and lightweight secret/command injection checks."""

    name = "security"
    category = "security"
    secret_name_pattern = re.compile(r"(api[_-]?key|secret|password|token)", re.IGNORECASE)
    weak_secret_values = {"secret", "changeme", "password", "123456", "jwt-secret"}

    def run(self, context: AgentContext) -> AgentResult:
        rule_engine = RuleEngine([SQLInjectionRule(), PathTraversalRule()])
        issues: list[Issue] = []
        for relative_path in context.files:
            file_path = relative_path.as_posix()
            source = read_python_source(context.project_root, relative_path)
            if source is None:
                continue
            issues.extend(rule_engine.review_source(file_path=file_path, source_code=source))
            tree = parse_python(file_path, source)
            if tree is not None:
                issues.extend(self._security_issues(file_path, tree))
        return AgentResult(agent_name=self.name, issues=dedupe_and_sort(issues))

    def _security_issues(self, file_path: str, tree: ast.AST) -> list[Issue]:
        issues: list[Issue] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Assign, ast.AnnAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                value = node.value
                for target in targets:
                    name = target.id if isinstance(target, ast.Name) else ""
                    if name and isinstance(value, ast.Constant) and isinstance(value.value, str):
                        lowered = value.value.lower()
                        if self.secret_name_pattern.search(name):
                            issues.append(self._issue("HardcodedSecretRisk", file_path, node.lineno, "Hardcoded secret-like value detected.", "Move secrets to a secure secret manager or environment variable."))
                        if name.upper() == "SECRET_KEY" and lowered in self.weak_secret_values:
                            issues.append(self._issue("JWTWeakSecretRisk", file_path, node.lineno, "Weak JWT secret value detected.", "Use a high-entropy secret managed outside source control."))
            elif isinstance(node, ast.Call):
                name = call_name(node.func)
                if name == "os.system" or name in {"subprocess.run", "subprocess.Popen", "subprocess.call"}:
                    shell_true = any(keyword.arg == "shell" and isinstance(keyword.value, ast.Constant) and keyword.value.value is True for keyword in node.keywords)
                    if name == "os.system" or shell_true:
                        issues.append(self._issue("CommandInjectionRisk", file_path, getattr(node, "lineno", 1), "Command execution may be vulnerable to injection.", "Avoid shell=True and pass validated argument lists to subprocess APIs."))
                if name == "jwt.encode" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant):
                    if isinstance(node.args[1].value, str) and node.args[1].value.lower() in self.weak_secret_values:
                        issues.append(self._issue("JWTWeakSecretRisk", file_path, getattr(node, "lineno", 1), "Weak JWT secret value detected.", "Use a high-entropy secret managed outside source control."))
        return issues

    @staticmethod
    def _issue(issue_type: str, file_path: str, line: int, message: str, suggestion: str) -> Issue:
        return Issue(severity="high", type=issue_type, file=file_path, line=line, message=message, suggestion=suggestion)
