"""Lightweight schemas for MCP tool inputs and outputs."""

from __future__ import annotations

from typing import Literal, TypedDict


Severity = Literal["critical", "high", "medium", "low"]


class ReviewFileInput(TypedDict, total=False):
    path: str
    config_path: str


class ReviewProjectInput(TypedDict, total=False):
    path: str
    enable_llm: bool
    llm_provider: str
    config_path: str
    enable_enterprise_rules: bool
    enable_agents: bool
    agents: list[str]
    network_policy: dict


class ReviewDiffInput(TypedDict):
    diff: str


class IssueOutput(TypedDict):
    severity: Severity
    type: str
    file: str
    line: int
    message: str
    suggestion: str


class ReviewResult(TypedDict):
    issues: list[IssueOutput]
