"""Typed models for GitHub PR review integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PullRequestEvent:
    installation_id: int
    owner: str
    repo: str
    pull_number: int
    head_sha: str
    base_sha: str = ""
    action: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def repository_full_name(self) -> str:
        return f"{self.owner}/{self.repo}"

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PullRequestEvent":
        repository = payload["repository"]
        pull_request = payload["pull_request"]
        owner = repository.get("owner", {}).get("login") or repository.get("owner", {}).get("name")
        return cls(
            installation_id=int(payload["installation"]["id"]),
            owner=str(owner),
            repo=str(repository["name"]),
            pull_number=int(pull_request["number"]),
            head_sha=str(pull_request["head"]["sha"]),
            base_sha=str(pull_request.get("base", {}).get("sha", "")),
            action=str(payload.get("action", "")),
            metadata={
                "action": str(payload.get("action", "")),
                "sender": str(payload.get("sender", {}).get("login", "")),
                "author": str(pull_request.get("user", {}).get("login", "")),
                "state": str(pull_request.get("state", "")),
                "base_sha": str(pull_request.get("base", {}).get("sha", "")),
                "head_sha": str(pull_request.get("head", {}).get("sha", "")),
            },
        )


@dataclass
class InlineComment:
    path: str
    line: int
    body: str
    side: str = "RIGHT"
    marker: str = ""


@dataclass
class GitHubReviewResult:
    status: str
    issues_count: int = 0
    summary_comment_id: int | None = None
    inline_comments_created: int = 0
    inline_comments_skipped: int = 0
    errors: list[str] = field(default_factory=list)
