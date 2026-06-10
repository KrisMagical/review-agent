import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

from app.llm.provider import AnthropicLLMProvider, LLMProviderError, OpenAILLMProvider
from app.reviewer import ReviewService
from reviewagent.connected import NetworkPolicy
from reviewagent.dashboard import app as dashboard_app_module
from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.models import PullRequestEvent
from reviewagent.integrations.github.reviewer import GitHubPullRequestReviewer
from reviewagent.mcp_server import tools
from reviewagent.storage import ReviewPersistenceService


def test_network_policy_defaults_deny_everything() -> None:
    policy = NetworkPolicy.offline()

    assert not policy.enabled
    assert not policy.allow_llm
    assert policy.code_sharing_mode == "none"
    assert not policy.allows_provider("openai")


def test_openai_provider_unauthed_does_not_attempt_http(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    provider = OpenAILLMProvider()

    with pytest.raises(LLMProviderError):
        provider.complete("prompt", policy=NetworkPolicy.offline())


def test_anthropic_provider_unauthed_and_authorized_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    called = {"value": False}

    def handler(request: httpx.Request) -> httpx.Response:
        called["value"] = True
        return httpx.Response(200, json={"content": [{"type": "text", "text": "{\"issues\": []}"}]})

    provider = AnthropicLLMProvider(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(LLMProviderError):
        provider.complete("prompt", policy=NetworkPolicy.offline())
    assert not called["value"]

    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    result = provider.complete(
        "prompt",
        policy=NetworkPolicy(enabled=True, allow_llm=True, code_sharing_mode="summary_only", allowed_providers=["anthropic"]),
    )
    assert result == "{\"issues\": []}"
    assert called["value"]


def test_mock_provider_runs_offline_and_real_provider_returns_safe_issue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "audit.db"))
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    mock_result = ReviewService().review_project(str(tmp_path), enable_llm=True, llm_provider="mock")
    assert "issues" in mock_result

    openai_result = ReviewService().review_project(str(tmp_path), enable_llm=True, llm_provider="openai")
    assert any(issue["type"] == "ArchitectureReviewError" for issue in openai_result["issues"])
    audits = ReviewPersistenceService(tmp_path / "audit.db").repository.list_network_audit()
    assert audits
    assert audits[0]["provider"] == "openai"
    assert "prompt" not in json.dumps(audits[0].get("metadata", {})).lower()


def test_cli_llm_openai_requires_explicit_network_authorization(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
    env = {**os.environ, "REVIEWAGENT_DB_PATH": str(tmp_path / "audit.db")}

    result = subprocess.run(
        [sys.executable, "-m", "reviewagent.cli.main", "project", str(project), "--llm", "--llm-provider", "openai", "--format", "json"],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    payload = json.loads(result.stdout)
    assert any(issue["type"] == "ArchitectureReviewError" for issue in payload["issues"])

    allowed = subprocess.run(
        [
            sys.executable,
            "-m",
            "reviewagent.cli.main",
            "project",
            str(project),
            "--llm",
            "--llm-provider",
            "openai",
            "--allow-network",
            "--allow-llm",
            "--code-sharing",
            "summary-only",
            "--format",
            "json",
        ],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    assert "issues" in json.loads(allowed.stdout)


def test_mcp_network_policy_reaches_review_service(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    result = tools.review_project(
        str(tmp_path),
        enable_llm=True,
        llm_provider="openai",
        network_policy={"enabled": False, "allow_llm": False, "code_sharing_mode": "none"},
    )

    assert any(issue["type"] == "ArchitectureReviewError" for issue in result["issues"])


class FakeGitHubClient:
    def __init__(self) -> None:
        self.files_called = False

    def get_installation_token(self, installation_id: int) -> str:
        return "token"

    def get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> str:
        return "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,1 @@\n+def run(): return 1\n"

    def list_pull_request_files(self, owner: str, repo: str, pull_number: int):
        self.files_called = True
        return [{"filename": "app.py", "content": "def run():\n    return 1\n"}]

    def get_repository_file_tree_for_ref(self, owner: str, repo: str, ref: str):
        self.files_called = True
        return {"tree": [{"path": "app.py", "type": "blob", "sha": "blob", "size": 25}], "truncated": False}

    def get_blob_text(self, owner: str, repo: str, blob_sha: str) -> str:
        return "def run():\n    return 1\n"


class FakeCommenter:
    def publish(self, event, result, diff_text, *, summary=True, inline=True, errors=None):
        return type("R", (), {"status": "completed", "issues_count": len(result["issues"]), "summary_comment_id": 1, "inline_comments_created": 0, "inline_comments_skipped": 0, "errors": list(errors or [])})()


def test_github_diff_only_default_and_full_project_mode() -> None:
    diff_client = FakeGitHubClient()
    diff_reviewer = GitHubPullRequestReviewer(
        client=diff_client,  # type: ignore[arg-type]
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s"),
        commenter=FakeCommenter(),  # type: ignore[arg-type]
    )
    event = PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="sha")
    assert diff_reviewer.review_pull_request(event).status == "completed"
    assert not diff_client.files_called

    full_client = FakeGitHubClient()
    full_reviewer = GitHubPullRequestReviewer(
        client=full_client,  # type: ignore[arg-type]
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s", review_mode="full_project"),
        commenter=FakeCommenter(),  # type: ignore[arg-type]
    )
    assert full_reviewer.review_pull_request(event).status == "completed"
    assert full_client.files_called


def test_dashboard_network_audit_api_and_no_secret_storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "audit.db"
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(db_path))
    service = ReviewPersistenceService(db_path)
    audit_id = service.save_network_audit(
        source="cli",
        provider="anthropic",
        operation="llm_architecture_review",
        code_sharing_mode="summary_only",
        status="success",
        metadata={"api_key": "secret", "prompt": "full prompt", "safe": "ok"},
    )

    records = dashboard_app_module.api_network_audit()
    detail = dashboard_app_module.api_network_audit_detail(audit_id)

    assert records
    assert detail["provider"] == "anthropic"
    serialized = json.dumps(detail)
    assert "secret" not in serialized
    assert "full prompt" not in serialized
    assert "ok" in serialized
