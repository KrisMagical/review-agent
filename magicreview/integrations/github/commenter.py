"""Publish magicreview PR comments while avoiding duplicates."""

from __future__ import annotations

from typing import Any

from magicreview.integrations.github.client import GitHubAppClient
from magicreview.integrations.github.formatter import SUMMARY_MARKER, format_inline_comment, format_summary_comment, inline_marker
from magicreview.integrations.github.mapper import DiffLineMapper
from magicreview.integrations.github.models import GitHubReviewResult, InlineComment, PullRequestEvent


class GitHubCommenter:
    def __init__(self, client: GitHubAppClient, *, max_inline_comments: int = 30) -> None:
        self.client = client
        self.max_inline_comments = max_inline_comments

    def upsert_summary(self, event: PullRequestEvent, result: dict[str, Any], *, errors: list[str] | None = None) -> int | None:
        body = format_summary_comment(result, errors=errors)
        comments = self.client.list_issue_comments(event.owner, event.repo, event.pull_number)
        existing = next((comment for comment in comments if SUMMARY_MARKER in str(comment.get("body", ""))), None)
        if existing:
            updated = self.client.update_issue_comment(event.owner, event.repo, int(existing["id"]), body)
            return int(updated.get("id", existing["id"]))
        created = self.client.create_issue_comment(event.owner, event.repo, event.pull_number, body)
        return int(created.get("id")) if created.get("id") is not None else None

    def build_inline_comments(self, result: dict[str, Any], mapper: DiffLineMapper) -> list[InlineComment]:
        comments: list[InlineComment] = []
        seen: set[str] = set()
        for issue in result.get("issues", []):
            marker = inline_marker(issue)
            if marker in seen:
                continue
            seen.add(marker)
            line = int(issue.get("line", 1))
            path = str(issue.get("file", ""))
            side = mapper.side_for(path, line)
            if side is None:
                continue
            comments.append(InlineComment(path=path, line=line, side=side, body=format_inline_comment(issue), marker=marker))
            if len(comments) >= self.max_inline_comments:
                break
        return comments

    def publish_inline_comments(self, event: PullRequestEvent, comments: list[InlineComment]) -> tuple[int, int]:
        existing_comments = self.client.list_review_comments(event.owner, event.repo, event.pull_number)
        existing_markers = {comment.marker for comment in comments if any(comment.marker in str(existing.get("body", "")) for existing in existing_comments)}
        created = 0
        skipped = 0
        for comment in comments:
            if comment.marker in existing_markers:
                skipped += 1
                continue
            self.client.create_review_comment(
                event.owner,
                event.repo,
                event.pull_number,
                body=comment.body,
                commit_id=event.head_sha,
                path=comment.path,
                line=comment.line,
                side=comment.side,
            )
            created += 1
        return created, skipped

    def publish(self, event: PullRequestEvent, result: dict[str, Any], diff_text: str, *, summary: bool = True, inline: bool = True, errors: list[str] | None = None) -> GitHubReviewResult:
        review_result = GitHubReviewResult(status="completed", issues_count=len(result.get("issues", [])), errors=list(errors or []))
        if summary:
            review_result.summary_comment_id = self.upsert_summary(event, result, errors=errors)
        if inline:
            comments = self.build_inline_comments(result, DiffLineMapper(diff_text))
            created, skipped = self.publish_inline_comments(event, comments)
            review_result.inline_comments_created = created
            review_result.inline_comments_skipped = skipped
        return review_result
