"""MCP tool functions backed by ReviewService."""

from __future__ import annotations

from typing import Any

from app.reviewer import ReviewService
from magicreview.mcp_server.schemas import ReviewResult


_service = ReviewService()


def set_review_service(service: ReviewService) -> None:
    """Replace the service instance, mainly for tests."""

    global _service
    _service = service


def review_file(path: str, config_path: str | None = None) -> ReviewResult:
    """Review a single Python file."""

    if not isinstance(path, str):
        return _argument_error("path must be a string")
    try:
        return _service.review_file(path, config_path=config_path)  # type: ignore[return-value]
    except TypeError:
        return _service.review_file(path)  # type: ignore[return-value]


def review_project(
    path: str,
    enable_llm: bool = False,
    llm_provider: str | None = None,
    config_path: str | None = None,
    enable_enterprise_rules: bool = True,
    enable_agents: bool = False,
    agents: list[str] | None = None,
    network_policy: dict[str, Any] | None = None,
) -> ReviewResult:
    """Review a project directory."""

    if not isinstance(path, str):
        return _argument_error("path must be a string")
    try:
        return _service.review_project(
            path,
            enable_llm=enable_llm,
            llm_provider=llm_provider,
            config_path=config_path,
            enable_enterprise_rules=enable_enterprise_rules,
            enable_agents=enable_agents,
            agents=agents,
            network_policy=network_policy,
        )  # type: ignore[return-value]
    except TypeError:
        return _service.review_project(path)  # type: ignore[return-value]


def review_diff(diff: str) -> ReviewResult:
    """Review a unified diff or patch string."""

    if not isinstance(diff, str):
        return _argument_error("diff must be a string")
    return _service.review_diff(diff)  # type: ignore[return-value]


def _argument_error(message: str) -> dict[str, list[dict[str, Any]]]:
    return {
        "issues": [
            {
                "severity": "low",
                "type": "ReviewError",
                "file": "<mcp>",
                "line": 1,
                "message": f"Invalid MCP tool argument: {message}.",
                "suggestion": "Pass arguments that match the MCP tool schema.",
            }
        ]
    }
