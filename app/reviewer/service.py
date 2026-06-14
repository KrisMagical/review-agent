"""Unified review service shared by CLI and MCP tools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.agents import ReviewCoordinator
from app.models.issue import Issue
from app.architecture import ArchitectureReviewer
from app.enterprise import EnterpriseRuleEngine, RuleConfigLoader
from app.llm.provider import provider_from_env
from app.parser import DiffParser, build_changed_source
from app.project.scanner import ProjectScanner
from app.reviewer.project_reviewer import ProjectReviewer
from app.rules.engine import RuleEngine
from magicreview.connected import NetworkPolicy


class ReviewService:
    """Stable facade for file, diff, and project review workflows."""

    max_file_size_bytes = 2 * 1024 * 1024
    max_diff_size_bytes = 5 * 1024 * 1024
    max_project_files = 2000
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}

    def __init__(
        self,
        *,
        rule_engine: RuleEngine | None = None,
        project_reviewer: ProjectReviewer | None = None,
        scanner: ProjectScanner | None = None,
        architecture_reviewer: ArchitectureReviewer | None = None,
        config_loader: RuleConfigLoader | None = None,
        coordinator: ReviewCoordinator | None = None,
    ) -> None:
        self.rule_engine = rule_engine or RuleEngine()
        self.project_reviewer = project_reviewer or ProjectReviewer()
        self.scanner = scanner or ProjectScanner()
        self.architecture_reviewer = architecture_reviewer
        self.config_loader = config_loader or RuleConfigLoader()
        self.coordinator = coordinator or ReviewCoordinator(scanner=self.scanner)

    def review_file(self, path: str, *, config_path: str | None = None) -> dict[str, list[dict[str, Any]]]:
        """Review one Python file and return a JSON-serializable report."""

        try:
            file_path = Path(path).expanduser()
            if not file_path.exists():
                return self._report([self._review_error(path, "Failed to review file: path does not exist.")])
            if not file_path.is_file():
                return self._report([self._review_error(path, "Failed to review file: path is not a file.")])
            if file_path.suffix != ".py":
                return self._report([self._review_error(path, "Failed to review file: only Python files are supported.")])
            if file_path.stat().st_size > self.max_file_size_bytes:
                return self._report(
                    [
                        Issue(
                            severity="low",
                            type="FileTooLarge",
                            file=str(path),
                            line=1,
                            message="File exceeds the maximum review size.",
                            suggestion="Review a smaller file or increase the service limit.",
                        )
                    ]
                )
            source = file_path.read_text(encoding="utf-8")
            issues = self.rule_engine.review_source(file_path=str(file_path), source_code=source)
            if config_path:
                config = self.config_loader.load(file_path.parent, config_path)
                issues.extend(config.errors)
                if config.has_rules:
                    issues.extend(EnterpriseRuleEngine(config).run_file(str(file_path), source))
            return self._report(self._dedupe_and_sort(issues))
        except UnicodeDecodeError:
            return self._report([self._review_error(path, "Failed to review file: file is not valid UTF-8 text.")])
        except OSError as exc:
            return self._report([self._review_error(path, f"Failed to review file: {exc.strerror or exc}")])
        except Exception as exc:
            return self._report([self._review_error(path, f"Failed to review file: {exc}")])

    def review_diff(self, diff: str) -> dict[str, list[dict[str, Any]]]:
        """Review a unified diff or patch text."""

        try:
            if not diff.strip():
                return {"issues": []}
            if len(diff.encode("utf-8")) > self.max_diff_size_bytes:
                return self._report(
                    [
                        Issue(
                            severity="low",
                            type="DiffTooLarge",
                            file="<diff>",
                            line=1,
                            message="Diff exceeds the maximum review size.",
                            suggestion="Review a smaller diff or increase the service limit.",
                        )
                    ]
                )
            issue_groups: list[list[Issue]] = []
            for file_path, file_diff in DiffParser.parse(diff).items():
                changed_lines = set(file_diff.all_changed_lines)
                source_code = build_changed_source(file_diff.added_lines)
                if not source_code.strip():
                    continue
                issue_groups.append(
                    self.rule_engine.review_source(
                        file_path=file_path,
                        source_code=source_code,
                        changed_lines=changed_lines,
                    )
                )
            return self._report(self._flatten(issue_groups))
        except Exception as exc:
            return self._report([self._review_error("<diff>", f"Failed to review diff: {exc}")])

    def review_project(
        self,
        path: str,
        *,
        enable_llm: bool = False,
        llm_provider: str | None = None,
        config_path: str | None = None,
        enable_enterprise_rules: bool = True,
        enable_agents: bool = False,
        agents: list[str] | None = None,
        network_policy: NetworkPolicy | dict[str, Any] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        """Review a project directory with Phase 1 and Phase 2 analyzers."""

        try:
            project_path = Path(path).expanduser()
            if not project_path.exists():
                return self._report([self._review_error(path, "Failed to review project: path does not exist.")])
            if not project_path.is_dir():
                return self._report([self._review_error(path, "Failed to review project: path is not a directory.")])
            files = self.scanner.scan(project_path)
            if len(files) > self.max_project_files:
                return self._report(
                    [
                        Issue(
                            severity="low",
                            type="ProjectTooLarge",
                            file=str(path),
                            line=1,
                            message="Project exceeds the maximum scanned file count.",
                            suggestion="Review a smaller project or configure exclusions.",
                        )
                    ]
                )
            active_policy = network_policy if isinstance(network_policy, NetworkPolicy) else NetworkPolicy.from_dict(network_policy)
            if enable_agents:
                context = self.coordinator.build_context(
                    project_path,
                    enable_llm=enable_llm,
                    llm_provider=llm_provider,
                    config_path=config_path,
                    enable_enterprise_rules=enable_enterprise_rules,
                    network_policy=active_policy,
                )
                return self.coordinator.review_project(project_path, context=context, selected_agents=agents)
            issues = self.project_reviewer.review(project_path)
            if enable_enterprise_rules:
                config = self.config_loader.load(project_path, config_path)
                issues.extend(config.errors)
                if config.has_rules:
                    issues.extend(EnterpriseRuleEngine(config).run_project(project_path, files))
            if enable_llm:
                reviewer = self.architecture_reviewer or ArchitectureReviewer(
                    provider=provider_from_env(llm_provider),
                    network_policy=active_policy,
                    audit_source="cli",
                    project_name=project_path.name,
                    target_ref=str(project_path),
                )
                issues.extend(reviewer.review_project(project_path, static_issues=issues))
            return self._report(self._dedupe_and_sort(issues))
        except Exception as exc:
            return self._report([self._review_error(path, f"Failed to review project: {exc}")])

    @staticmethod
    def _report(issues: list[Issue]) -> dict[str, list[dict[str, Any]]]:
        return {"issues": [issue.to_dict() for issue in issues]}

    @classmethod
    def _dedupe_and_sort(cls, issues: list[Issue]) -> list[Issue]:
        unique: dict[tuple[str, str, int, str], Issue] = {}
        for issue in issues:
            key = (issue.type, issue.file, issue.line, issue.message)
            existing = unique.get(key)
            if existing is None or cls.severity_order[issue.severity] < cls.severity_order[existing.severity]:
                unique[key] = issue
        return sorted(unique.values(), key=lambda issue: (cls.severity_order[issue.severity], issue.file, issue.line, issue.type))

    @staticmethod
    def _flatten(groups: list[list[Issue]]) -> list[Issue]:
        return [issue for group in groups for issue in group]

    @staticmethod
    def _review_error(file_path: str, message: str) -> Issue:
        return Issue(
            severity="low",
            type="ReviewError",
            file=file_path or "<unknown>",
            line=1,
            message=message,
            suggestion="Check that the path exists and contains valid Python code.",
        )
