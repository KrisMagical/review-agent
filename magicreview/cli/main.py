"""Lightweight MagicReview console entry point.

This module intentionally avoids importing the legacy ``app.main`` module while
rendering help or version output.  The legacy module still owns the command
implementation for now, but it pulls optional integrations such as GitHub HTTP
publishing; those imports should not be required for ``mgreview --help`` from a
minimal wheel install.
"""

from __future__ import annotations

import argparse
from typing import Sequence

from magicreview import __version__
from magicreview.config.env import get_env


def build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mgreview",
        description="MagicReview: local-first, self-hostable AI code review platform.",
        epilog=(
            "Examples:\n"
            "  mgreview file app/main.py\n"
            "  mgreview diff\n"
            "  mgreview project .\n"
            "  mgreview dashboard serve\n"
            "  mgreview --version"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"MagicReview {__version__}")
    parser.add_argument("--debug", action="store_true", help="Print detailed CLI errors to stderr.")
    subparsers = parser.add_subparsers(dest="command")

    file_parser = subparsers.add_parser("file", help="Review one Python file.")
    file_parser.add_argument("target", nargs="?", help="Python file to review.")
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
    project_parser.add_argument(
        "--llm-provider",
        choices=("none", "mock", "openai", "anthropic", "azure_openai"),
        default=None,
        help="LLM provider for architecture review.",
    )
    project_parser.add_argument("--allow-network", action="store_true", help="Allow explicitly approved network operations.")
    project_parser.add_argument("--allow-llm", action="store_true", help="Allow network LLM providers when --allow-network is also set.")
    project_parser.add_argument("--allow-github", action="store_true", help="Allow GitHub API operations for connected workflows.")
    project_parser.add_argument(
        "--code-sharing",
        choices=("summary-only", "snippets", "full-context"),
        default="none",
        help="Maximum code sharing mode for connected providers.",
    )
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

    dashboard_parser = subparsers.add_parser("dashboard", help="Manage and serve the MagicReview Dashboard.")
    dashboard_subparsers = dashboard_parser.add_subparsers(dest="dashboard_command")
    dashboard_subparsers.add_parser("init-db", help="Initialize the Dashboard SQLite database.")
    serve_parser = dashboard_subparsers.add_parser("serve", help="Start the Dashboard server.")
    serve_parser.add_argument("--host", default=get_env("DASHBOARD_HOST", "127.0.0.1"))
    serve_parser.add_argument("--port", type=int, default=int(get_env("DASHBOARD_PORT", "8080") or "8080"))

    subparsers.add_parser("mcp", help="Start the MagicReview MCP stdio server.")
    github_app_parser = subparsers.add_parser("github-app", help="Manage and serve the MagicReview GitHub App.")
    github_app_subparsers = github_app_parser.add_subparsers(dest="github_app_command")
    github_app_subparsers.add_parser("serve", help="Start the GitHub App webhook server.")
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_cli_parser()
    args, _unknown = parser.parse_known_args(argv)
    if args.command is None:
        parser.print_help()
        return
    if args.command == "mcp":
        from magicreview.mcp_server.server import main as mcp_main

        mcp_main()
        return
    if args.command == "github-app":
        if getattr(args, "github_app_command", None) in {None, "serve"}:
            from magicreview.integrations.github.app import main as github_app_main

            github_app_main()
            return
        parser.error("github-app requires a subcommand: serve")

    from app.main import main as legacy_main

    legacy_main()


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--format", "-f", choices=("json", "terminal", "markdown", "html"), default="json", help="Report output format.")
    parser.add_argument("--output", "-o", help="Write the report to a file instead of stdout.")
    parser.add_argument("--severity", choices=("low", "medium", "high", "critical"), help="Minimum severity to include.")
    parser.add_argument("--max-issues", type=int, help="Maximum number of issues to output.")
    parser.add_argument("--fail-on", choices=("low", "medium", "high", "critical"), help="Exit with code 1 when this severity or higher is present.")
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors.")
    parser.add_argument("--debug", action="store_true", help="Print detailed CLI errors to stderr.")


if __name__ == "__main__":
    main()
