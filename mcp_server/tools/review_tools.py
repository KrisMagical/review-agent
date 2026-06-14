"""Asynchronous review tools for MCP clients."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from magicreview.mcp_server import tools as service_tools


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ToolSpec:
    """MCP tool metadata independent from a concrete SDK implementation."""

    name: str
    description: str
    input_schema: dict[str, Any]


REVIEW_FILE_TOOL = ToolSpec(
    name="review_file",
    description="Reviews a single Python file for code quality, bugs, architecture anomalies, and type safety leaks.",
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The absolute or relative system path to the target Python file.",
            },
            "config_path": {
                "type": "string",
                "description": "Optional enterprise rule config file path.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
)

REVIEW_PROJECT_TOOL = ToolSpec(
    name="review_project",
    description=(
        "Performs a full project-wide structural and static analysis review, including circular dependency graphs "
        "and God Object checks."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "The root path of the project directory to evaluate.",
            },
            "enable_llm": {
                "type": "boolean",
                "description": "Enable optional LLM architecture review. Defaults to false.",
                "default": False,
            },
            "llm_provider": {
                "type": "string",
                "description": "Optional architecture LLM provider: none, mock, or openai.",
            },
            "config_path": {
                "type": "string",
                "description": "Optional enterprise rule config file path.",
            },
            "enable_enterprise_rules": {
                "type": "boolean",
                "description": "Enable enterprise rule config loading. Defaults to true.",
                "default": True,
            },
            "enable_agents": {
                "type": "boolean",
                "description": "Enable Phase 6 multi-agent project review. Defaults to false.",
                "default": False,
            },
            "agents": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional agent subset, such as ['quality', 'security'].",
            },
            "network_policy": {
                "type": "object",
                "description": "Optional connected-services NetworkPolicy. Defaults to offline.",
            },
        },
        "required": ["path"],
        "additionalProperties": False,
    },
)

REVIEW_DIFF_TOOL = ToolSpec(
    name="review_diff",
    description="Analyzes a raw Git diff string or patch snippet to flag introduced regressions and styling violations in changed lines.",
    input_schema={
        "type": "object",
        "properties": {
            "diff": {
                "type": "string",
                "description": "The raw unified diff string to analyze.",
            }
        },
        "required": ["diff"],
        "additionalProperties": False,
    },
)


def list_review_tools() -> list[ToolSpec]:
    """Return all magicreview MCP tool specifications."""

    return [REVIEW_FILE_TOOL, REVIEW_PROJECT_TOOL, REVIEW_DIFF_TOOL]


async def review_file(arguments: dict[str, Any]) -> str:
    """Review one Python file and return the unified JSON report."""

    path = _required_string(arguments, "path")
    config_path = arguments.get("config_path")
    if config_path is not None and not isinstance(config_path, str):
        raise ValueError("Argument `config_path` must be a string when provided.")
    return await _run_engine(lambda: json.dumps(service_tools.review_file(path, config_path=config_path), ensure_ascii=False, indent=2))


async def review_project(arguments: dict[str, Any]) -> str:
    """Review an entire project and return the unified JSON report."""

    path = _required_string(arguments, "path")
    enable_llm = bool(arguments.get("enable_llm", False))
    llm_provider = arguments.get("llm_provider")
    if llm_provider is not None and not isinstance(llm_provider, str):
        raise ValueError("Argument `llm_provider` must be a string when provided.")
    config_path = arguments.get("config_path")
    if config_path is not None and not isinstance(config_path, str):
        raise ValueError("Argument `config_path` must be a string when provided.")
    enable_enterprise_rules = bool(arguments.get("enable_enterprise_rules", True))
    enable_agents = bool(arguments.get("enable_agents", False))
    agents = arguments.get("agents")
    if agents is not None and not (isinstance(agents, list) and all(isinstance(agent, str) for agent in agents)):
        raise ValueError("Argument `agents` must be a list of strings when provided.")
    network_policy = arguments.get("network_policy")
    if network_policy is not None and not isinstance(network_policy, dict):
        raise ValueError("Argument `network_policy` must be an object when provided.")
    return await _run_engine(
        lambda: json.dumps(
            service_tools.review_project(
                path,
                enable_llm=enable_llm,
                llm_provider=llm_provider,
                config_path=config_path,
                enable_enterprise_rules=enable_enterprise_rules,
                enable_agents=enable_agents,
                agents=agents,
                network_policy=network_policy,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )


async def review_diff(arguments: dict[str, Any]) -> str:
    """Review a raw unified diff and return the unified JSON report."""

    diff = _required_string(arguments, "diff", allow_empty=True)
    return await _run_engine(lambda: json.dumps(service_tools.review_diff(diff), ensure_ascii=False, indent=2))


async def call_review_tool(name: str, arguments: dict[str, Any] | None) -> str:
    """Dispatch an MCP tool call to the matching review implementation."""

    payload = arguments or {}
    match name:
        case "review_file":
            return await review_file(payload)
        case "review_project":
            return await review_project(payload)
        case "review_diff":
            return await review_diff(payload)
        case _:
            raise ValueError(f"Unknown magicreview tool: {name}")


def error_report(message: str) -> str:
    """Return a JSON report carrying a tool execution error."""

    return json.dumps(
        {
            "issues": [],
            "error": {
                "message": message,
            },
        },
        ensure_ascii=False,
        indent=2,
    )


async def _run_engine(func: Callable[[], str]) -> str:
    """Run blocking analyzers off the event loop while keeping stdout isolated."""

    def guarded_call() -> str:
        with contextlib.redirect_stdout(sys.stderr):
            return func()

    try:
        return await asyncio.to_thread(guarded_call)
    except Exception as exc:
        logger.exception("magicreview MCP tool execution failed.")
        return error_report(str(exc))


def _required_string(arguments: dict[str, Any], key: str, *, allow_empty: bool = False) -> str:
    value = arguments.get(key)
    if not isinstance(value, str):
        raise ValueError(f"Argument `{key}` must be a string.")
    if not allow_empty and not value.strip():
        raise ValueError(f"Argument `{key}` must be a non-empty string.")
    return value
