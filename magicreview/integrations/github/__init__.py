"""GitHub App integration for magicreview Phase 8."""

from magicreview.integrations.github.config import GitHubAppConfig
from magicreview.integrations.github.reviewer import GitHubPullRequestReviewer
from magicreview.integrations.github.webhook import GitHubWebhookHandler

__all__ = ["GitHubAppConfig", "GitHubPullRequestReviewer", "GitHubWebhookHandler"]
