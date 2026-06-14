"""GitHub webhook event handling."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from magicreview.integrations.github.config import GitHubAppConfig
from magicreview.integrations.github.models import PullRequestEvent
from magicreview.integrations.github.reviewer import GitHubPullRequestReviewer
from magicreview.integrations.github.security import verify_signature


SUPPORTED_PULL_REQUEST_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


class GitHubWebhookHandler:
    def __init__(self, *, config: GitHubAppConfig, reviewer: GitHubPullRequestReviewer | None = None) -> None:
        self.config = config
        self.reviewer = reviewer

    def handle(self, *, payload_bytes: bytes, signature: str | None, event_name: str | None) -> tuple[int, dict[str, Any]]:
        if not verify_signature(payload_bytes, signature, self.config.webhook_secret):
            return 401, {"status": "unauthorized"}
        if event_name != "pull_request":
            return 200, {"status": "ignored", "reason": f"unsupported event: {event_name}"}
        try:
            payload = json.loads(payload_bytes.decode("utf-8"))
        except json.JSONDecodeError:
            return 200, {"status": "ignored", "reason": "invalid json payload"}
        action = str(payload.get("action", ""))
        if action not in SUPPORTED_PULL_REQUEST_ACTIONS:
            return 200, {"status": "ignored", "reason": f"unsupported action: {action}"}
        try:
            event = PullRequestEvent.from_payload(payload)
        except (KeyError, TypeError, ValueError):
            return 200, {"status": "failed", "reason": "payload missing required pull_request fields"}
        reviewer = self.reviewer or GitHubPullRequestReviewer.from_config(self.config)
        result = reviewer.review_pull_request(event)
        return 200, {"status": result.status, "result": asdict(result)}
