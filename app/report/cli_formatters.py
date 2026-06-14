"""Human and machine output formatters for the magicreview CLI."""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from typing import Any, Iterable


SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_ORDER = {severity: index for index, severity in enumerate(SEVERITIES)}


def summarize(issues: Iterable[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}
    for issue in issues:
        severity = str(issue.get("severity", "low")).lower()
        if severity not in SEVERITY_ORDER:
            severity = "low"
        summary["total"] += 1
        summary[severity] += 1
    return summary


def normalize_result(result: dict[str, Any]) -> dict[str, Any]:
    issues = list(result.get("issues", []))
    return {"issues": issues, "summary": summarize(issues)}


def filter_issues(
    result: dict[str, Any],
    *,
    minimum_severity: str | None = None,
    max_issues: int | None = None,
) -> dict[str, Any]:
    issues = list(result.get("issues", []))
    if minimum_severity:
        threshold = SEVERITY_ORDER[minimum_severity]
        issues = [issue for issue in issues if SEVERITY_ORDER.get(str(issue.get("severity", "low")).lower(), 3) <= threshold]
    if max_issues is not None:
        issues = issues[: max(0, max_issues)]
    return normalize_result({"issues": issues})


def has_fail_on_issue(result: dict[str, Any], fail_on: str | None) -> bool:
    if not fail_on:
        return False
    threshold = SEVERITY_ORDER[fail_on]
    return any(SEVERITY_ORDER.get(str(issue.get("severity", "low")).lower(), 3) <= threshold for issue in result.get("issues", []))


class BaseCliFormatter:
    def format(self, result: dict[str, Any]) -> str:
        raise NotImplementedError


class JsonReportFormatter(BaseCliFormatter):
    def format(self, result: dict[str, Any]) -> str:
        return json.dumps(normalize_result(result), ensure_ascii=False, indent=2)


class TerminalReportFormatter(BaseCliFormatter):
    def __init__(self, *, use_color: bool = False) -> None:
        self.use_color = use_color

    def format(self, result: dict[str, Any]) -> str:
        normalized = normalize_result(result)
        summary = normalized["summary"]
        lines = [
            "MagicReview Report",
            "",
            "Summary:",
            f"  Critical: {summary['critical']}",
            f"  High: {summary['high']}",
            f"  Medium: {summary['medium']}",
            f"  Low: {summary['low']}",
            "",
            "Issues:",
        ]
        if not normalized["issues"]:
            lines.append("  No issues found.")
            return "\n".join(lines)
        for issue in normalized["issues"]:
            severity = str(issue["severity"]).upper()
            lines.extend(
                [
                    "",
                    f"[{severity}] {issue['type']}",
                    f"  File: {issue['file']}:{issue['line']}",
                    f"  Message: {issue['message']}",
                    f"  Suggestion: {issue['suggestion']}",
                ]
            )
        return "\n".join(lines)


class MarkdownReportFormatter(BaseCliFormatter):
    def format(self, result: dict[str, Any]) -> str:
        normalized = normalize_result(result)
        summary = normalized["summary"]
        lines = [
            "# MagicReview Report",
            "",
            "## Summary",
            "",
            "| Severity | Count |",
            "|---|---:|",
            f"| Critical | {summary['critical']} |",
            f"| High | {summary['high']} |",
            f"| Medium | {summary['medium']} |",
            f"| Low | {summary['low']} |",
            "",
            "## Issues",
        ]
        if not normalized["issues"]:
            lines.extend(["", "No issues found."])
            return "\n".join(lines)
        for issue in normalized["issues"]:
            lines.extend(
                [
                    "",
                    f"### {str(issue['severity']).upper()} {issue['type']}",
                    "",
                    f"- File: `{issue['file']}:{issue['line']}`",
                    f"- Message: {issue['message']}",
                    f"- Suggestion: {issue['suggestion']}",
                ]
            )
        return "\n".join(lines)


class HtmlReportFormatter(BaseCliFormatter):
    def format(self, result: dict[str, Any]) -> str:
        normalized = normalize_result(result)
        summary = normalized["summary"]
        rows = "\n".join(
            "<tr>"
            f"<td class=\"sev-{html.escape(str(issue['severity']))}\">{html.escape(str(issue['severity']).upper())}</td>"
            f"<td>{html.escape(str(issue['type']))}</td>"
            f"<td><code>{html.escape(str(issue['file']))}:{html.escape(str(issue['line']))}</code></td>"
            f"<td>{html.escape(str(issue['message']))}</td>"
            f"<td>{html.escape(str(issue['suggestion']))}</td>"
            "</tr>"
            for issue in normalized["issues"]
        )
        if not rows:
            rows = "<tr><td colspan=\"5\">No issues found.</td></tr>"
        return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>MagicReview Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 32px; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f3f4f6; }}
    .sev-critical, .sev-high {{ color: #b91c1c; font-weight: 700; }}
    .sev-medium {{ color: #92400e; font-weight: 700; }}
    .sev-low {{ color: #1d4ed8; font-weight: 700; }}
    code {{ background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>MagicReview Report</h1>
  <h2>Summary</h2>
  <table>
    <tr><th>Severity</th><th>Count</th></tr>
    <tr><td>Critical</td><td>{summary['critical']}</td></tr>
    <tr><td>High</td><td>{summary['high']}</td></tr>
    <tr><td>Medium</td><td>{summary['medium']}</td></tr>
    <tr><td>Low</td><td>{summary['low']}</td></tr>
  </table>
  <h2>Issues</h2>
  <table>
    <tr><th>Severity</th><th>Type</th><th>File</th><th>Message</th><th>Suggestion</th></tr>
    {rows}
  </table>
</body>
</html>"""


@dataclass(frozen=True)
class FormatterFactory:
    use_color: bool = False

    def create(self, name: str) -> BaseCliFormatter:
        if name == "json":
            return JsonReportFormatter()
        if name == "terminal":
            return TerminalReportFormatter(use_color=self.use_color)
        if name == "markdown":
            return MarkdownReportFormatter()
        if name == "html":
            return HtmlReportFormatter()
        raise ValueError(f"Unsupported output format: {name}")
