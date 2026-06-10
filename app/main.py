#!/usr/bin/env python3
"""CLI and FastAPI entry points for the PR review agent."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

try:
    from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Request, status
except ModuleNotFoundError:
    class _MissingFastAPI:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def get(self, *_args: Any, **_kwargs: Any):
            return lambda func: func

        def post(self, *_args: Any, **_kwargs: Any):
            return lambda func: func

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class _Status:
        HTTP_202_ACCEPTED = 202
        HTTP_400_BAD_REQUEST = 400
        HTTP_401_UNAUTHORIZED = 401
        HTTP_500_INTERNAL_SERVER_ERROR = 500

    def Header(*_args: Any, default: Any = None, **_kwargs: Any) -> Any:  # type: ignore[no-redef]
        return default

    BackgroundTasks = Any  # type: ignore[assignment, misc]
    FastAPI = _MissingFastAPI  # type: ignore[assignment, misc]
    Request = Any  # type: ignore[assignment, misc]
    status = _Status()  # type: ignore[assignment]

from app.analyzers import ASTAnalyzer, ComplexityAnalyzer, DependencyAnalyzer, RuffAdapter
from app.llm import LLMReviewer
from app.parser import DiffParser, build_changed_source, get_diff_from_file, get_diff_from_stdin, read_python_file
from app.report import ReportFormatter, ReviewIssue
from app.report.cli_formatters import FormatterFactory, filter_issues, has_fail_on_issue
from app.report.github_publisher import GitHubPublisher, GitHubPublisherError
from app.reviewer import ProjectReviewer, ReviewService
from app.rules import RuffLintRule
from app.rules.architecture import GodObjectDetector
from app.rules.base import Issue
from app.rules.engine import RuleEngine
from reviewagent import __version__
from reviewagent.storage import ReviewPersistenceService, init_db
from reviewagent.connected import NetworkPolicy


WORKSPACE_ROOT = Path(os.getcwd()).resolve()
logger = logging.getLogger(__name__)
app = FastAPI(title="pr-review-agent")


def resolve_workspace_path(file_path: str) -> Path:
    """Resolve a diff path and reject absolute or workspace-escaping paths."""

    candidate = Path(file_path)
    if candidate.is_absolute():
        raise ValueError("Unsafe path traversal detected")

    resolved_path = (WORKSPACE_ROOT / candidate).resolve()
    try:
        resolved_path.relative_to(WORKSPACE_ROOT)
    except ValueError as exc:
        raise ValueError("Unsafe path traversal detected") from exc

    return resolved_path


def read_file_content(file_path: str | Path) -> str:
    """Read a changed file for local analysis."""

    try:
        return resolve_workspace_path(str(file_path)).read_text(encoding="utf-8")
    except ValueError:
        raise
    except OSError:
        return ""


def issue_from_dict(issue: dict[str, Any]) -> Issue:
    """Convert analyzer dictionaries into the legacy Issue model."""

    return Issue(
        severity=issue["severity"],
        type=issue["type"],
        file=issue["file"],
        line=issue["line"],
        message=issue["message"],
        suggestion=issue.get("suggestion", "") if hasattr(issue, "get") else issue["suggestion"],
    )


def build_llm_context(diff_map: dict[str, Any]) -> str:
    """Collect changed file contents for semantic LLM review context."""

    context_blocks: list[str] = []
    for file_path in diff_map.keys():
        content = read_file_content(file_path)
        if content:
            context_blocks.append(f"# File: {file_path}\n{content}")
    return "\n\n".join(context_blocks)


def build_llm_context_from_contents(file_contents: dict[str, str]) -> str:
    """Collect GitHub-fetched changed file contents for semantic review."""

    return "\n\n".join(
        f"# File: {file_path}\n{content}"
        for file_path, content in file_contents.items()
        if content
    )


def review_diff_text(
    diff_text: str,
    *,
    file_contents: dict[str, str] | None = None,
    skip_llm: bool = True,
) -> list[ReviewIssue]:
    """Run all review stages for a unified diff."""

    if not diff_text.strip():
        return []

    diff_map = DiffParser.parse(diff_text)
    changed_lines_per_file = {
        file_path: set(file_diff.all_changed_lines)
        for file_path, file_diff in diff_map.items()
    }

    ruff_rule = RuffLintRule()
    ast_analyzer = ASTAnalyzer()
    complexity_analyzer = ComplexityAnalyzer()
    llm_reviewer = LLMReviewer() if not skip_llm else None

    issue_groups: list[list[Any]] = []
    content_by_file = file_contents or {}

    for file_path, file_diff in diff_map.items():
        content = content_by_file.get(file_path)
        if content is None:
            content = read_file_content(file_path)
        if not content:
            continue

        changed_lines = changed_lines_per_file.get(file_path, set())

        ruff_issues = [
            issue
            for issue in ruff_rule.analyze(file_path, content)
            if issue.line in changed_lines
        ]
        issue_groups.append(ruff_issues)

        ast_issues = [
            issue_from_dict(issue)
            for issue in ast_analyzer.analyze_file(file_path, content)
        ]
        ast_issues = [issue for issue in ast_issues if issue.line in changed_lines]
        issue_groups.append(ast_issues)

        complexity_issues = [
            issue_from_dict(issue)
            for issue in complexity_analyzer.analyze_diff_files(
                [
                    {
                        "file": file_path,
                        "added_lines": file_diff.added_lines,
                        "source_code": content,
                    }
                ]
            )
        ]
        issue_groups.append(complexity_issues)

    if llm_reviewer:
        llm_context = (
            build_llm_context_from_contents(content_by_file)
            if content_by_file
            else build_llm_context(diff_map)
        )
        llm_issues = llm_reviewer.review(diff_text, context=llm_context)
        validated_llm = []
        for issue in llm_issues:
            lines = changed_lines_per_file.get(issue.file, set())
            if issue.line is None or lines:
                validated_llm.append(issue)
        issue_groups.append(validated_llm)

    return ReportFormatter.merge_and_filter(issue_groups, changed_lines_per_file)


def review_project_path(project_dir: str | Path = ".") -> list[ReviewIssue]:
    """Run Phase 1 and Phase 2 static analysis for a project."""

    return ReportFormatter.merge_and_filter([ProjectReviewer().review(project_dir)])


def review_file_path(file_path: str | Path) -> list[ReviewIssue]:
    """Run Phase 1 static rules for one Python file."""

    normalized_path, content = read_python_file(file_path)
    return ReportFormatter.merge_and_filter([RuleEngine().review_source(file_path=normalized_path, source_code=content)])


def review_diff_phase1(diff_text: str) -> list[ReviewIssue]:
    """Run Phase 1 rules against added Python lines from a unified diff."""

    engine = RuleEngine()
    issue_groups: list[list[Issue]] = []
    for file_path, file_diff in DiffParser.parse(diff_text).items():
        changed_lines = set(file_diff.all_changed_lines)
        source_code = build_changed_source(file_diff.added_lines)
        if not source_code.strip():
            continue
        issues = engine.review_source(
            file_path=file_path,
            source_code=source_code,
            changed_lines=changed_lines,
        )
        issue_groups.append(issues)
    return ReportFormatter.merge_and_filter(issue_groups)


def verify_github_signature(payload: bytes, signature_header: str | None, secret: str) -> bool:
    """Verify GitHub's X-Hub-Signature-256 HMAC header."""

    if not signature_header or not signature_header.startswith("sha256="):
        return False

    expected = "sha256=" + hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
) -> dict[str, str]:
    """Receive GitHub pull_request webhook events and enqueue review work."""

    secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook secret is not configured.")

    payload_bytes = await request.body()
    if not verify_github_signature(payload_bytes, x_hub_signature_256, secret):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid GitHub webhook signature.")

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": "unsupported event"}

    try:
        payload = json.loads(payload_bytes)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON payload.") from exc

    action = payload.get("action")
    if action not in {"opened", "synchronize"}:
        return {"status": "ignored", "reason": f"unsupported action: {action}"}

    background_tasks.add_task(process_pull_request_review, payload)
    return {"status": "accepted"}


async def process_pull_request_review(payload: dict[str, Any]) -> None:
    """Fetch PR data, run review, and publish GitHub comments."""

    token = os.getenv("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN is not configured; cannot publish PR review.")
        return

    try:
        repository = payload["repository"]["full_name"]
        pull_request = payload["pull_request"]
        pull_number = int(pull_request["number"])
        head_sha = str(pull_request["head"]["sha"])
    except (KeyError, TypeError, ValueError):
        logger.error("Malformed pull_request webhook payload.", exc_info=True)
        return

    publisher = GitHubPublisher(token)
    try:
        diff_text = await publisher.fetch_pull_request_diff(repository, pull_number)
        diff_map = DiffParser.parse(diff_text)
        file_contents = await publisher.fetch_file_contents(repository, diff_map.keys(), ref=head_sha)
        issues = review_diff_text(diff_text, file_contents=file_contents, skip_llm=True)
        await publisher.publish_review(
            repository=repository,
            pull_number=pull_number,
            commit_id=head_sha,
            issues=issues,
        )
    except GitHubPublisherError:
        logger.error("GitHub API integration failed.", exc_info=True)
    except Exception:
        logger.exception("Unexpected PR review failure.")


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="review",
        description="ReviewAgent local CLI for file, diff, project, enterprise, LLM, and multi-agent reviews.",
    )
    parser.add_argument("--version", action="version", version=f"ReviewAgent {__version__}")
    parser.add_argument("--debug", action="store_true", help="Print detailed CLI errors to stderr.")
    subparsers = parser.add_subparsers(dest="command")

    file_parser = subparsers.add_parser("file", help="Review one Python file.")
    file_parser.add_argument("target", help="Python file to review.")
    _add_output_options(file_parser)
    file_parser.add_argument("--config", help="Enterprise rule YAML or JSON config path.")
    file_parser.add_argument("--save", action="store_true", help="Save review result to the Dashboard SQLite database.")

    diff_parser = subparsers.add_parser("diff", help="Review a unified diff from stdin or a patch file.")
    _add_output_options(diff_parser)
    diff_parser.add_argument("--file", dest="diff_file", help="Read diff content from a patch file.")
    diff_parser.add_argument("--diff-file", dest="diff_file", help=argparse.SUPPRESS)
    diff_parser.add_argument("--save", action="store_true", help="Save review result to the Dashboard SQLite database.")

    project_parser = subparsers.add_parser("project", help="Review a Python project directory.")
    project_parser.add_argument("target", nargs="?", default=".", help="Project directory to review.")
    _add_output_options(project_parser)
    project_parser.add_argument("--config", help="Enterprise rule YAML or JSON config path.")
    project_parser.add_argument("--no-enterprise", action="store_true", help="Disable enterprise rule loading.")
    project_parser.add_argument("--llm", action="store_true", help="Enable optional LLM architecture review.")
    project_parser.add_argument("--llm-provider", choices=("none", "mock", "openai", "anthropic", "azure_openai"), default=None, help="LLM provider for architecture review.")
    project_parser.add_argument("--allow-network", action="store_true", help="Allow explicitly approved network operations.")
    project_parser.add_argument("--allow-llm", action="store_true", help="Allow network LLM providers when --allow-network is also set.")
    project_parser.add_argument("--allow-github", action="store_true", help="Allow GitHub API operations for connected workflows.")
    project_parser.add_argument("--code-sharing", choices=("summary-only", "snippets", "full-context"), default="none", help="Maximum code sharing mode for connected providers.")
    project_parser.add_argument("--confirm-network", action="store_true", help="Confirm that connected services may run under the selected policy.")
    project_parser.add_argument("--audit-network", action="store_true", default=True, help="Record network audit events.")
    project_parser.add_argument(
        "--agents",
        nargs="?",
        const="all",
        default=None,
        help="Enable multi-agent review. Optionally pass a comma-separated subset, e.g. quality,bug,security.",
    )
    project_parser.add_argument("--save", action="store_true", help="Save review result to the Dashboard SQLite database.")

    dashboard_parser = subparsers.add_parser("dashboard", help="Manage and serve the ReviewAgent Dashboard.")
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_command")
    dashboard_subparsers.add_parser("init-db", help="Initialize the Dashboard SQLite database.")
    serve_parser = dashboard_subparsers.add_parser("serve", help="Start the Dashboard server.")
    serve_parser.add_argument("--host", default=os.getenv("REVIEWAGENT_DASHBOARD_HOST", "127.0.0.1"))
    serve_parser.add_argument("--port", type=int, default=int(os.getenv("REVIEWAGENT_DASHBOARD_PORT", "8080")))
    return parser


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", "-f", choices=("json", "terminal", "markdown", "html"), default="json", help="Report output format.")
    parser.add_argument("--output", "-o", help="Write the report to a file instead of stdout.")
    parser.add_argument("--severity", choices=("low", "medium", "high", "critical"), help="Minimum severity to include.")
    parser.add_argument("--max-issues", type=int, help="Maximum number of issues to output.")
    parser.add_argument("--fail-on", choices=("low", "medium", "high", "critical"), help="Exit with code 1 when this severity or higher is present.")
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors.")
    parser.add_argument("--debug", action="store_true", help="Print detailed CLI errors to stderr.")


def main() -> None:
    parser = build_cli_parser()
    args = parser.parse_args()
    service = ReviewService()
    try:
        if args.command == "file":
            result = service.review_file(args.target, config_path=args.config)
        elif args.command == "project":
            selected_agents = _parse_agents(args.agents)
            result = service.review_project(
                args.target,
                enable_llm=args.llm,
                llm_provider=args.llm_provider,
                config_path=args.config,
                enable_enterprise_rules=not args.no_enterprise,
                enable_agents=args.agents is not None,
                agents=selected_agents,
                network_policy=_network_policy_from_args(args),
            )
            if args.save:
                _save_review_result(result, source="cli", target_type="project", target_ref=args.target, project_name=Path(args.target).name or args.target)
        elif args.command == "diff":
            diff_text = get_diff_from_file(args.diff_file) if args.diff_file else get_diff_from_stdin()
            result = service.review_diff(diff_text)
            if args.save:
                _save_review_result(result, source="cli", target_type="diff", target_ref=args.diff_file or "<stdin>")
        elif args.command == "dashboard":
            if args.dashboard_command == "init-db":
                init_db()
                print(json.dumps({"status": "ok", "message": "Dashboard database initialized."}, ensure_ascii=False, indent=2), file=sys.stdout)
                raise SystemExit(0)
            if args.dashboard_command == "serve":
                os.environ["REVIEWAGENT_DASHBOARD_HOST"] = args.host
                os.environ["REVIEWAGENT_DASHBOARD_PORT"] = str(args.port)
                from reviewagent.dashboard.app import main as dashboard_main

                dashboard_main()
                raise SystemExit(0)
            parser.error("dashboard requires a subcommand: init-db or serve")
        else:
            diff_text = get_diff_from_stdin()
            result = service.review_diff(diff_text)
            args.format = "json"
            args.output = None
            args.severity = None
            args.max_issues = None
            args.fail_on = None
            args.no_color = True
            args.save = False
        if args.command == "file" and args.save:
            _save_review_result(result, source="cli", target_type="file", target_ref=args.target, project_name=Path(args.target).parent.name or None)
        filtered = filter_issues(result, minimum_severity=args.severity, max_issues=args.max_issues)
        rendered = FormatterFactory(use_color=not args.no_color).create(args.format).format(filtered)
        if args.output:
            Path(args.output).write_text(rendered, encoding="utf-8")
        else:
            print(rendered, file=sys.stdout)
        raise SystemExit(1 if has_fail_on_issue(filtered, args.fail_on) else 0)
    except SystemExit:
        raise
    except Exception as exc:
        if getattr(args, "debug", False):
            import traceback

            traceback.print_exc(file=sys.stderr)
        print(f"ReviewAgent CLI error: {exc}", file=sys.stderr)
        raise SystemExit(2)


def _parse_agents(raw_agents: str | None) -> list[str] | None:
    if raw_agents in (None, "all"):
        return None
    return [item.strip() for item in raw_agents.split(",") if item.strip()]


def _network_policy_from_args(args: Any) -> NetworkPolicy:
    provider = getattr(args, "llm_provider", None)
    allowed = [provider] if provider and provider not in {"none", "mock"} else []
    return NetworkPolicy(
        enabled=bool(getattr(args, "allow_network", False)),
        allow_llm=bool(getattr(args, "allow_llm", False)),
        allow_github_api=bool(getattr(args, "allow_github", False)),
        allow_remote_mcp=False,
        code_sharing_mode=str(getattr(args, "code_sharing", "none")).replace("-", "_"),  # type: ignore[arg-type]
        allowed_providers=allowed,
        require_explicit_consent=True,
        audit_enabled=bool(getattr(args, "audit_network", True)),
    )


def _save_review_result(
    result: dict[str, Any],
    *,
    source: str,
    target_type: str,
    target_ref: str,
    project_name: str | None = None,
    repository_url: str | None = None,
    commit_sha: str | None = None,
    pull_request_number: int | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    try:
        ReviewPersistenceService().save_review_result(
            result,
            source=source,
            target_type=target_type,
            target_ref=target_ref,
            project_name=project_name,
            repository_url=repository_url,
            commit_sha=commit_sha,
            pull_request_number=pull_request_number,
            metadata=metadata,
        )
    except Exception as exc:
        logger.warning("Failed to save review result: %s", exc)


if __name__ == "__main__":
    main()
