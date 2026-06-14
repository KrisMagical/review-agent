"""Ruff execution adapter for file and project static analysis."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from app.models.issue import Issue
from app.project.scanner import ProjectScanner


RuffDiagnostic = dict[str, Any]


class RuffAdapter:
    """Run ``ruff check`` and normalize diagnostics into ``Issue`` objects."""

    def __init__(
        self,
        ruff_executable: str = "ruff",
        *,
        workspace_root: str | Path | None = None,
        timeout_seconds: int = 60,
        emit_unavailable_issue: bool = False,
    ) -> None:
        self.ruff_executable = ruff_executable
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.timeout_seconds = timeout_seconds
        self.emit_unavailable_issue = emit_unavailable_issue
        self._unavailable_message: str | None = None

    def check_file(self, file_path: str | Path, *, added_lines: object | None = None) -> list[Issue]:
        issues = self._issues_for_target(file_path)
        if added_lines is None:
            return issues
        line_numbers = self.normalize_added_line_numbers(added_lines)
        return [issue for issue in issues if issue.line in line_numbers]

    def check_project(self, project_dir: str | Path = ".") -> list[Issue]:
        root = self._resolve_path(project_dir)
        if root.is_dir():
            files = [root / relative_path for relative_path in ProjectScanner().scan(root)]
            if not files:
                return []
            return self._issues_for_targets(files)
        return self._issues_for_target(root)

    def analyze_diff_files(self, diff_results: list[dict[str, Any]]) -> list[Issue]:
        issues: list[Issue] = []
        for diff_result in diff_results:
            file_path = diff_result.get("file") or diff_result.get("file_path") or diff_result.get("path")
            if isinstance(file_path, str) and file_path.endswith(".py"):
                issues.extend(self.check_file(file_path, added_lines=diff_result.get("added_lines")))
        return issues

    def _issues_for_target(self, target: str | Path) -> list[Issue]:
        diagnostics = self._run_ruff_json(self._resolve_path(target))
        if diagnostics is None:
            return self._unavailable_issue("Ruff is not available.")
        return [self._diagnostic_to_issue(item, fallback_file=str(target)) for item in diagnostics]

    def _issues_for_targets(self, targets: list[Path]) -> list[Issue]:
        diagnostics = self._run_ruff_json_targets(targets)
        if diagnostics is None:
            return self._unavailable_issue("Ruff is not available.")
        return [self._diagnostic_to_issue(item, fallback_file=str(targets[0])) for item in diagnostics]

    def _run_ruff_json(self, target: Path) -> list[RuffDiagnostic] | None:
        return self._run_ruff_json_targets([target])

    def _run_ruff_json_targets(self, targets: list[Path]) -> list[RuffDiagnostic] | None:
        commands = [
            [self.ruff_executable, "check", *(str(target) for target in targets), "--output-format", "json"],
            [self.ruff_executable, "check", *(str(target) for target in targets), "--format", "json"],
        ]
        last_result: subprocess.CompletedProcess[str] | None = None
        for command in commands:
            try:
                result = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.timeout_seconds,
                    check=False,
                )
            except FileNotFoundError:
                self._unavailable_message = "Ruff is not available."
                return None
            except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                self._unavailable_message = "Ruff execution failed."
                return None

            last_result = result
            stderr = result.stderr or ""
            if result.returncode == 2 and ("unexpected argument" in stderr or "unexpected option" in stderr):
                continue
            break

        if last_result is None:
            return []
        if last_result.returncode not in (0, 1):
            return []
        if not last_result.stdout.strip():
            return []
        try:
            payload = json.loads(last_result.stdout)
        except json.JSONDecodeError:
            return []
        return [item for item in payload if isinstance(item, dict)] if isinstance(payload, list) else []

    def _diagnostic_to_issue(self, item: RuffDiagnostic, *, fallback_file: str) -> Issue:
        code = str(item.get("code") or "RUFF")
        location = item.get("location") if isinstance(item.get("location"), dict) else {}
        issue_type, severity, suggestion = self._map_code(code)
        message = str(item.get("message") or "Ruff reported a style issue.")
        return Issue(
            severity=severity,
            type=issue_type,
            file=self._display_file_path(str(item.get("filename") or fallback_file)),
            line=self._positive_int(location.get("row"), default=1),
            message=f"{code}: {message}",
            suggestion=suggestion,
        )

    @staticmethod
    def _map_code(code: str) -> tuple[str, str, str]:
        normalized = code.upper()
        if normalized == "F401":
            return "RuffUnusedImport", "low", "Remove unused imports."
        if normalized == "F841":
            return "RuffUnusedVariable", "low", "Remove unused variables or use them intentionally."
        if normalized.startswith("I"):
            return "RuffImportOrder", "low", "Sort imports according to project style."
        if normalized.startswith("N"):
            return "RuffNaming", "medium", "Rename the symbol to follow Python naming conventions."
        if normalized.startswith(("E", "W")):
            return "RuffStyle", "low", "Fix the style issue reported by Ruff."
        return "RuffStyle", "low", "Fix the issue reported by Ruff."

    def _unavailable_issue(self, message: str) -> list[Issue]:
        if not self.emit_unavailable_issue:
            return []
        return [
            Issue(
                severity="low",
                type="AnalyzerUnavailable",
                file="<project>",
                line=1,
                message=message,
                suggestion="Install ruff to enable style and lint checks.",
            )
        ]

    def _resolve_path(self, path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else (self.workspace_root / candidate).resolve()

    def _display_file_path(self, filename: str) -> str:
        path = Path(filename)
        try:
            return path.resolve().relative_to(self.workspace_root).as_posix()
        except (OSError, ValueError):
            return filename.replace("\\", "/")

    @staticmethod
    def _positive_int(value: Any, *, default: int) -> int:
        return value if isinstance(value, int) and value > 0 else default

    @staticmethod
    def normalize_added_line_numbers(added_lines: object) -> set[int]:
        if not isinstance(added_lines, list | tuple | set):
            return set()
        line_numbers: set[int] = set()
        for item in added_lines:
            match item:
                case int(line):
                    line_numbers.add(line)
                case {"line": int(line)} | {"line_num": int(line)} | {"new_line": int(line)}:
                    line_numbers.add(line)
                case (int(start), int(end)):
                    low, high = sorted((start, end))
                    line_numbers.update(range(low, high + 1))
                case [int(start), int(end)]:
                    low, high = sorted((start, end))
                    line_numbers.update(range(low, high + 1))
                case (int(line), _):
                    line_numbers.add(line)
                case [int(line), *_]:
                    line_numbers.add(line)
                case _:
                    continue
        return {line for line in line_numbers if line > 0}
