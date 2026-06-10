import base64
import json
from pathlib import Path

import httpx

from reviewagent.dashboard.hosted_review import HostedReviewService
from reviewagent.integrations.github.client import GitHubAppClient, GitHubClientError
from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.formatter import format_summary_comment
from reviewagent.integrations.github.models import PullRequestEvent
from reviewagent.integrations.github.repository_fetcher import GitHubRepositoryFetcher
from reviewagent.integrations.github.reviewer import GitHubPullRequestReviewer


def encoded(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def sample_diff() -> str:
    return "diff --git a/app/main.py b/app/main.py\n--- a/app/main.py\n+++ b/app/main.py\n@@ -0,0 +1,1 @@\n+print('x')\n"


def tree_payload() -> dict:
    return {
        "tree": [
            {"path": "app/main.py", "type": "blob", "sha": "py", "size": 32},
            {"path": "reviewagent.yml", "type": "blob", "sha": "cfg", "size": 10},
            {"path": ".env", "type": "blob", "sha": "env", "size": 10},
            {"path": "node_modules/x.py", "type": "blob", "sha": "skip", "size": 10},
        ],
        "truncated": False,
    }


def test_review_mode_config_defaults_full_project_and_invalid(monkeypatch) -> None:
    monkeypatch.delenv("REVIEWAGENT_GITHUB_REVIEW_MODE", raising=False)
    assert GitHubAppConfig.from_env().review_mode == "diff_only"
    monkeypatch.setenv("REVIEWAGENT_GITHUB_REVIEW_MODE", "full_project")
    assert GitHubAppConfig.from_env().review_mode == "full_project"
    monkeypatch.setenv("REVIEWAGENT_GITHUB_REVIEW_MODE", "wat")
    assert GitHubAppConfig.from_env().review_mode == "diff_only"


def test_github_client_tree_blob_and_errors_are_mocked() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/git/blobs/py" in request.url.path:
            return httpx.Response(200, json={"encoding": "base64", "content": encoded("print('x')\n")})
        if "/missing" in request.url.path:
            return httpx.Response(404, json={})
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json=tree_payload())
        return httpx.Response(403, json={})

    client = GitHubAppClient(app_id="1", private_key="test", token="t", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert client.get_tree("octo", "repo", "sha")["tree"]
    assert client.get_blob_text("octo", "repo", "py") == "print('x')\n"
    try:
            client.get_blob_text("octo", "repo", "missing")
    except GitHubClientError as exc:
        assert "403" in str(exc) or "404" in str(exc)
    else:
        raise AssertionError("GitHubClientError expected")


def test_repository_fetcher_filters_files_limits_and_cleans_temp(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json=tree_payload())
        sha = request.url.path.rsplit("/", 1)[-1]
        content = "rules: {}\n" if sha == "cfg" else "print('x')\n"
        return httpx.Response(200, json={"encoding": "base64", "content": encoded(content)})

    client = GitHubAppClient(app_id="1", private_key="test", token="t", http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    fetcher = GitHubRepositoryFetcher(client, GitHubAppConfig(max_project_files=10, max_file_bytes=100, max_project_bytes=1000))
    workspace = fetcher.fetch_pull_request_project("octo", "repo", "sha")
    root = workspace.root
    assert (root / "app/main.py").exists()
    assert (root / "reviewagent.yml").exists()
    assert not (root / ".env").exists()
    assert not (root / "node_modules/x.py").exists()
    workspace.cleanup()
    assert not root.exists()


def test_repository_fetcher_rejects_truncated_and_unsafe_paths() -> None:
    def truncated(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"tree": [], "truncated": True})

    client = GitHubAppClient(app_id="1", private_key="test", token="t", http_client=httpx.Client(transport=httpx.MockTransport(truncated)))
    fetcher = GitHubRepositoryFetcher(client, GitHubAppConfig())
    try:
        fetcher.fetch_pull_request_project("octo", "repo", "sha")
    except GitHubClientError as exc:
        assert "truncated" in str(exc)
    else:
        raise AssertionError("truncated tree should fail")


class FakeProjectReviewService:
    def __init__(self) -> None:
        self.project_calls = []
        self.diff_calls = []

    def review_diff(self, diff: str) -> dict:
        self.diff_calls.append(diff)
        return {"issues": []}

    def review_project(self, path: str, **kwargs) -> dict:
        self.project_calls.append((path, kwargs))
        return {
            "issues": [
                {"severity": "high", "type": "GodFile", "file": "app/main.py", "line": 1, "message": "Project issue", "suggestion": "Split it."},
                {"severity": "medium", "type": "ProjectLevel", "file": "app/other.py", "line": 99, "message": "Summary only", "suggestion": "Review it."},
            ]
        }


def test_pull_request_reviewer_full_project_calls_review_project_and_summary_has_mode() -> None:
    comments = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "token"})
        if request.headers.get("Accept") == "application/vnd.github.v3.diff":
            return httpx.Response(200, text=sample_diff())
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"tree": [{"path": "app/main.py", "type": "blob", "sha": "py", "size": 20}], "truncated": False})
        if "/git/blobs/py" in request.url.path:
            return httpx.Response(200, json={"encoding": "base64", "content": encoded("print('x')\n")})
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/issues/7/comments") and request.method == "POST":
            comments.append(json.loads(request.content.decode("utf-8"))["body"])
            return httpx.Response(201, json={"id": 1})
        if request.url.path.endswith("/pulls/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/pulls/7/comments") and request.method == "POST":
            return httpx.Response(201, json={"id": 2})
        return httpx.Response(200, json={})

    service = FakeProjectReviewService()
    reviewer = GitHubPullRequestReviewer(
        client=GitHubAppClient(app_id="1", private_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler))),
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s", review_mode="full_project", enable_agents=True),
        review_service=service,  # type: ignore[arg-type]
    )
    result = reviewer.review_pull_request(PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="head"))

    assert result.status == "completed"
    assert service.project_calls
    assert service.project_calls[0][1]["enable_agents"] is True
    assert service.project_calls[0][1]["enable_llm"] is False
    assert "Review mode: `full_project`" in comments[0]


def test_pull_request_reviewer_full_project_fetch_error_returns_issue() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/access_tokens"):
            return httpx.Response(201, json={"token": "token"})
        if request.headers.get("Accept") == "application/vnd.github.v3.diff":
            return httpx.Response(200, text=sample_diff())
        if "/git/trees/" in request.url.path:
            return httpx.Response(500, json={})
        if request.url.path.endswith("/issues/7/comments") and request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path.endswith("/issues/7/comments") and request.method == "POST":
            body = json.loads(request.content.decode("utf-8"))["body"]
            assert "GitHubProjectFetchError" in body
            return httpx.Response(201, json={"id": 1})
        if request.url.path.endswith("/pulls/7/comments"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={})

    reviewer = GitHubPullRequestReviewer(
        client=GitHubAppClient(app_id="1", private_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler))),
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s", review_mode="full_project"),
    )
    result = reviewer.review_pull_request(PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="head"))
    assert result.status == "completed"


def test_format_summary_comment_includes_review_mode() -> None:
    body = format_summary_comment({"metadata": {"review_mode": "full_project"}, "issues": []})
    assert "Review mode: `full_project`" in body


def test_hosted_review_github_pr_full_project_mock_success(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "db.sqlite"))
    monkeypatch.setenv("GITHUB_TOKEN", "token")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/pulls/7") and request.headers.get("Accept") != "application/vnd.github.v3.diff":
            return httpx.Response(200, json={"head": {"sha": "head"}, "base": {"sha": "base"}})
        if "/git/trees/" in request.url.path:
            return httpx.Response(200, json={"tree": [{"path": "app/main.py", "type": "blob", "sha": "py", "size": 20}], "truncated": False})
        if "/git/blobs/py" in request.url.path:
            return httpx.Response(200, json={"encoding": "base64", "content": encoded("print('x')\n")})
        return httpx.Response(200, text=sample_diff())

    service = HostedReviewService(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = service.review_github_pr(
        "https://github.com/octo/repo/pull/7",
        {"allow_network": True, "review_mode": "full_project", "save_result": True, "enable_agents": True},
    )
    assert result.ok is True
    assert result.review_run_id
