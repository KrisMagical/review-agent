import asyncio
import json

import httpx

from reviewagent.integrations.github.app import app, health
from reviewagent.integrations.github.client import GitHubAppClient
from reviewagent.integrations.github.commenter import GitHubCommenter
from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.formatter import SUMMARY_MARKER, format_inline_comment, format_summary_comment, inline_marker
from reviewagent.integrations.github.mapper import DiffLineMapper
from reviewagent.integrations.github.models import GitHubReviewResult, PullRequestEvent
from reviewagent.integrations.github.reviewer import GitHubPullRequestReviewer
from reviewagent.integrations.github.security import compute_signature, verify_signature
from reviewagent.integrations.github.webhook import GitHubWebhookHandler


def sample_payload(action: str = "opened") -> dict:
    return {
        "action": action,
        "installation": {"id": 123},
        "repository": {"name": "repo", "owner": {"login": "octo"}},
        "pull_request": {
            "number": 7,
            "head": {"sha": "head-sha"},
            "base": {"sha": "base-sha"},
        },
    }


def sample_diff() -> str:
    return (
        "diff --git a/app/db.py b/app/db.py\n"
        "--- a/app/db.py\n"
        "+++ b/app/db.py\n"
        "@@ -1,2 +1,3 @@\n"
        " def ok():\n"
        "+    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
        "-    old()\n"
        "     return 1\n"
        "diff --git a/app/other.py b/app/other.py\n"
        "--- a/app/other.py\n"
        "+++ b/app/other.py\n"
        "@@ -0,0 +1,1 @@\n"
        "+print('x')\n"
    )


def test_signature_verification() -> None:
    payload = b'{"ok": true}'
    secret = "secret"
    signature = compute_signature(payload, secret)

    assert verify_signature(payload, signature, secret)
    assert not verify_signature(payload, "sha256=bad", secret)
    assert not verify_signature(payload, None, secret)


class FakeReviewer:
    def __init__(self) -> None:
        self.events = []

    def review_pull_request(self, event: PullRequestEvent) -> GitHubReviewResult:
        self.events.append(event)
        return GitHubReviewResult(status="completed", issues_count=1)


def test_webhook_handler_processes_supported_pull_request_and_ignores_others() -> None:
    config = GitHubAppConfig(webhook_secret="secret")
    reviewer = FakeReviewer()
    handler = GitHubWebhookHandler(config=config, reviewer=reviewer)  # type: ignore[arg-type]
    payload = json.dumps(sample_payload()).encode("utf-8")
    signature = compute_signature(payload, "secret")

    status_code, body = handler.handle(payload_bytes=payload, signature=signature, event_name="pull_request")
    assert status_code == 200
    assert body["status"] == "completed"
    assert reviewer.events[0].pull_number == 7

    ignored_payload = json.dumps(sample_payload("closed")).encode("utf-8")
    ignored_status, ignored_body = handler.handle(
        payload_bytes=ignored_payload,
        signature=compute_signature(ignored_payload, "secret"),
        event_name="pull_request",
    )
    assert ignored_status == 200
    assert ignored_body["status"] == "ignored"

    event_status, event_body = handler.handle(payload_bytes=payload, signature=signature, event_name="push")
    assert event_status == 200
    assert event_body["status"] == "ignored"


def test_webhook_handler_rejects_bad_signature_and_handles_missing_fields() -> None:
    config = GitHubAppConfig(webhook_secret="secret")
    handler = GitHubWebhookHandler(config=config, reviewer=FakeReviewer())  # type: ignore[arg-type]
    payload = b"{}"

    assert handler.handle(payload_bytes=payload, signature=None, event_name="pull_request")[0] == 401
    status_code, body = handler.handle(
        payload_bytes=payload,
        signature=compute_signature(payload, "secret"),
        event_name="pull_request",
    )
    assert status_code == 200
    assert body["status"] in {"ignored", "failed"}


def test_github_client_jwt_and_api_calls_are_mocked() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.method, str(request.url)))
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "installation-token"})
        if request.headers.get("Accept") == "application/vnd.github.v3.diff":
            return httpx.Response(200, text=sample_diff())
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/issues/7/comments") and request.method == "POST":
            return httpx.Response(201, json={"id": 10})
        if request.url.path.endswith("/pulls/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/pulls/7/comments") and request.method == "POST":
            return httpx.Response(201, json={"id": 11})
        if request.url.path.endswith("/check-runs"):
            return httpx.Response(201, json={"id": 12})
        return httpx.Response(200, json={"id": 13})

    client = GitHubAppClient(app_id="1", private_key="test-private-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))

    assert client.create_jwt().count(".") == 2
    assert client.get_installation_token(123) == "installation-token"
    assert "SELECT *" in client.get_pull_request_diff("octo", "repo", 7)
    assert client.create_issue_comment("octo", "repo", 7, "body")["id"] == 10
    assert client.create_review_comment("octo", "repo", 7, body="b", commit_id="sha", path="a.py", line=1)["id"] == 11
    assert client.create_check_run("octo", "repo", name="ReviewAgent", head_sha="sha", conclusion="success", summary="ok")["id"] == 12
    assert seen


def test_diff_line_mapping_added_deleted_and_multifile() -> None:
    mapper = DiffLineMapper(sample_diff())

    assert mapper.can_comment("app/db.py", 2)
    assert mapper.side_for("app/db.py", 2) == "RIGHT"
    assert not mapper.can_comment("app/db.py", 3)
    assert mapper.can_comment("app/other.py", 1)
    assert mapper.side_for("app/missing.py", 1) is None


def test_comment_formatters_and_dedup_markers() -> None:
    result = {
        "issues": [
            {"severity": "high", "type": "SQLInjectionRule", "file": "app/db.py", "line": 2, "message": "SQL", "suggestion": "Use params."}
        ]
    }
    issue = result["issues"][0]

    assert SUMMARY_MARKER in format_summary_comment(result)
    assert inline_marker(issue) == inline_marker(issue)
    assert inline_marker(issue) in format_inline_comment(issue)


def test_commenter_upserts_summary_and_skips_duplicate_inline() -> None:
    calls = {"patch": 0, "post_inline": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[{"id": 99, "body": SUMMARY_MARKER}])
        if request.url.path.endswith("/issues/comments/99") and request.method == "PATCH":
            calls["patch"] += 1
            return httpx.Response(200, json={"id": 99})
        if request.url.path.endswith("/pulls/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[{"body": "<!-- reviewagent-inline:SQLInjectionRule:app/db.py:2 -->"}])
        if request.url.path.endswith("/pulls/7/comments") and request.method == "POST":
            calls["post_inline"] += 1
            return httpx.Response(201, json={"id": 1})
        return httpx.Response(200, json={})

    client = GitHubAppClient(app_id="1", private_key="test", token="t", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    commenter = GitHubCommenter(client, max_inline_comments=30)
    event = PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="sha")
    result = {"issues": [{"severity": "high", "type": "SQLInjectionRule", "file": "app/db.py", "line": 2, "message": "SQL", "suggestion": "Use params."}]}

    published = commenter.publish(event, result, sample_diff())

    assert published.summary_comment_id == 99
    assert published.inline_comments_created == 0
    assert published.inline_comments_skipped == 1
    assert calls["patch"] == 1
    assert calls["post_inline"] == 0


class FakeReviewService:
    def __init__(self) -> None:
        self.diff = ""

    def review_diff(self, diff: str) -> dict:
        self.diff = diff
        return {
            "issues": [
                {"severity": "high", "type": "SQLInjectionRule", "file": "app/db.py", "line": 2, "message": "SQL", "suggestion": "Use params."},
                {"severity": "medium", "type": "Other", "file": "app/db.py", "line": 99, "message": "Other", "suggestion": "Other."},
            ]
        }


def test_pull_request_reviewer_calls_review_service_and_limits_inline_comments() -> None:
    created_inline = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "token"})
        if request.headers.get("Accept") == "application/vnd.github.v3.diff":
            return httpx.Response(200, text=sample_diff())
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/issues/7/comments") and request.method == "POST":
            return httpx.Response(201, json={"id": 33})
        if request.url.path.endswith("/pulls/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/pulls/7/comments") and request.method == "POST":
            created_inline.append(json.loads(request.content.decode("utf-8")))
            return httpx.Response(201, json={"id": 34})
        return httpx.Response(200, json={})

    client = GitHubAppClient(app_id="1", private_key="test-private-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    service = FakeReviewService()
    reviewer = GitHubPullRequestReviewer(
        client=client,
        config=GitHubAppConfig(app_id="1", private_key="test-private-key", webhook_secret="s", max_inline_comments=1),
        review_service=service,  # type: ignore[arg-type]
    )
    result = reviewer.review_pull_request(PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="sha"))

    assert "SELECT *" in service.diff
    assert result.summary_comment_id == 33
    assert result.inline_comments_created == 1
    assert len(created_inline) == 1
    assert created_inline[0]["path"] == "app/db.py"


def test_pull_request_reviewer_handles_github_api_failure() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    client = GitHubAppClient(app_id="1", private_key="test-private-key", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    reviewer = GitHubPullRequestReviewer(client=client, config=GitHubAppConfig(app_id="1", private_key="test-private-key", webhook_secret="s"))

    result = reviewer.review_pull_request(PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="sha"))

    assert result.status == "failed"
    assert result.errors


def test_health_function_returns_ok() -> None:
    assert asyncio.run(health()) == {"status": "ok", "service": "github-app"}
    assert app is not None
