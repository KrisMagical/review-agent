"""LLM architecture reviewer."""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import ValidationError

from app.architecture.context_builder import ArchitectureContextBuilder
from app.models.issue import Issue
from app.llm.provider import LLMProvider, LLMProviderError, provider_from_env
from magicreview.connected import NetworkPolicy
from magicreview.storage import ReviewPersistenceService


class ArchitectureReviewer:
    """Build context, call an LLM provider, and normalize architecture issues."""

    allowed_severities = {"critical", "high", "medium", "low"}

    def __init__(
        self,
        provider: LLMProvider | None = None,
        context_builder: ArchitectureContextBuilder | None = None,
        *,
        max_issues: int = 50,
        network_policy: NetworkPolicy | None = None,
        audit_source: str = "cli",
        project_name: str | None = None,
        target_ref: str | None = None,
    ) -> None:
        self.provider = provider or provider_from_env()
        self.context_builder = context_builder or ArchitectureContextBuilder()
        self.max_issues = max_issues
        self.network_policy = network_policy or NetworkPolicy.offline()
        self.audit_source = audit_source
        self.project_name = project_name
        self.target_ref = target_ref

    def review_project(self, project_root: str | Path, static_issues: list[Issue] | None = None) -> list[Issue]:
        status = "success"
        error_type = None
        try:
            context = self.context_builder.build(project_root, static_issues=static_issues or [])
            prompt = self.render_prompt(context.to_prompt_text(self.context_builder.max_context_chars))
            try:
                raw = self.provider.complete(prompt, policy=self.network_policy)
            except TypeError:
                raw = self.provider.complete(prompt)  # type: ignore[call-arg]
            return self._dedupe(self._parse_issues(raw, project_root))[: self.max_issues]
        except Exception as exc:
            status = "failed"
            error_type = type(exc).__name__
            return [self._error_issue(exc)]
        finally:
            self._audit(status=status, error_type=error_type)

    @staticmethod
    def render_prompt(context_text: str) -> str:
        template_path = Path(__file__).resolve().parents[1] / "llm" / "prompts" / "architecture_review.md"
        try:
            template = template_path.read_text(encoding="utf-8")
        except OSError:
            template = "Return only JSON with an issues array. severity must be critical/high/medium/low.\n{{ARCHITECTURE_CONTEXT}}"
        return template.replace("{{ARCHITECTURE_CONTEXT}}", context_text)

    def _parse_issues(self, text: str, project_root: str | Path) -> list[Issue]:
        try:
            payload = json.loads(self._extract_json(text))
        except json.JSONDecodeError as exc:
            raise LLMProviderError("LLM architecture review returned invalid JSON.") from exc
        raw_issues = payload.get("issues") if isinstance(payload, dict) else None
        if not isinstance(raw_issues, list):
            raise LLMProviderError("LLM architecture review returned an invalid schema.")

        valid_files = self._valid_files(project_root)
        issues: list[Issue] = []
        for raw in raw_issues[: self.max_issues * 2]:
            if not isinstance(raw, dict):
                continue
            if raw.get("severity", "").lower() not in self.allowed_severities:
                continue
            file_path = str(raw.get("file") or "<project>")
            if file_path not in {"<project>", ""} and valid_files and file_path.replace("\\", "/") not in valid_files:
                continue
            try:
                issues.append(
                    Issue(
                        severity=str(raw["severity"]).lower(),
                        type=str(raw["type"])[:80],
                        file=file_path or "<project>",
                        line=int(raw.get("line") or 1),
                        message=str(raw["message"])[:500],
                        suggestion=str(raw["suggestion"])[:500],
                    )
                )
            except (KeyError, TypeError, ValueError, ValidationError):
                continue
        return issues

    @staticmethod
    def _extract_json(text: str) -> str:
        fenced = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        return text.strip()

    @staticmethod
    def _valid_files(project_root: str | Path) -> set[str]:
        root = Path(project_root).resolve()
        try:
            return {path.relative_to(root).as_posix() for path in root.rglob("*.py")}
        except OSError:
            return set()

    @staticmethod
    def _dedupe(issues: list[Issue]) -> list[Issue]:
        seen: set[tuple[str, str, int, str]] = set()
        result: list[Issue] = []
        for issue in issues:
            key = (issue.type, issue.file, issue.line, issue.message)
            if key in seen:
                continue
            seen.add(key)
            result.append(issue)
        return result

    @staticmethod
    def _error_issue(exc: Exception) -> Issue:
        return Issue(
            severity="low",
            type="ArchitectureReviewError",
            file="<project>",
            line=1,
            message="LLM architecture review failed or is not configured.",
            suggestion="Configure MGREVIEW_LLM_PROVIDER and API credentials, or run without --llm.",
        )

    def _audit(self, *, status: str, error_type: str | None) -> None:
        if not self.network_policy.audit_enabled:
            return
        if not self.network_policy.enabled and not getattr(self.provider, "requires_network", False):
            return
        try:
            ReviewPersistenceService().save_network_audit(
                source=self.audit_source,
                provider=getattr(self.provider, "name", self.provider.__class__.__name__),
                operation="llm_architecture_review",
                code_sharing_mode=self.network_policy.code_sharing_mode,
                project_name=self.project_name,
                target_ref=self.target_ref,
                status=status,
                error_type=error_type,
                metadata={"requires_network": getattr(self.provider, "requires_network", False)},
            )
        except Exception:
            pass
