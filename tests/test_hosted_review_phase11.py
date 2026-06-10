import json
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from reviewagent.dashboard import app as dashboard_app_module
from reviewagent.dashboard.hosted_review import HostedReviewService, ensure_allowed_path, parse_github_pr_url
from reviewagent.storage.repository import ReviewRepository


def auth_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "hosted.db"))
    monkeypatch.setenv("REVIEWAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("REVIEWAGENT_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("REVIEWAGENT_API_KEYS", "dev-token")
    monkeypatch.setenv("REVIEWAGENT_ALLOWED_REVIEW_ROOTS", str(tmp_path))


def sample_diff() -> str:
    return "diff --git a/app.py b/app.py\n--- a/app.py\n+++ b/app.py\n@@ -0,0 +1,2 @@\n+def run(x):\n+    return x + 42\n"


def test_review_pages_require_auth_and_render_after_login(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)

    assert client.get("/review", follow_redirects=False).status_code == 303
    client.post("/login", data={"username": "admin", "password": "password", "next": "/review"})

    assert client.get("/review").status_code == 200
    assert client.get("/review/diff").status_code == 200
    assert client.get("/review/project").status_code == 200
    assert client.get("/review/github-pr").status_code == 200
    assert "full_context may send" in client.get("/review/project").text


def test_post_diff_text_save_and_no_save(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)
    headers = {"Authorization": "Bearer dev-token"}

    saved = client.post("/api/review/diff", headers=headers, json={"diff_text": sample_diff(), "save_result": True})
    assert saved.status_code == 200
    payload = saved.json()
    assert payload["ok"] is True
    assert payload["review_run_id"]
    assert ReviewRepository(tmp_path / "hosted.db").list_reviews(source="dashboard")
    metadata = ReviewRepository(tmp_path / "hosted.db").list_reviews(source="dashboard")[0]["metadata"]
    assert "diff --git" not in json.dumps(metadata)

    not_saved = client.post("/api/review/diff", headers=headers, json={"diff_text": sample_diff(), "save_result": False})
    assert not_saved.status_code == 200
    assert not_saved.json()["review_run_id"] is None


def test_diff_upload_empty_and_too_large(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    monkeypatch.setenv("REVIEWAGENT_MAX_UPLOAD_BYTES", "20")
    client = TestClient(dashboard_app_module.app)
    client.post("/login", data={"username": "admin", "password": "password", "next": "/review/diff"})

    empty = client.post("/review/diff", data={"diff_text": "", "save_result": "on"})
    assert empty.status_code == 400
    assert "Diff is required" in empty.text

    oversized = client.post(
        "/review/diff",
        files={"diff_file": ("change.patch", sample_diff().encode("utf-8"), "text/plain")},
        data={"save_result": "on"},
    )
    assert oversized.status_code == 400
    assert "Diff is required" in oversized.text or "maximum upload" in oversized.text


def test_project_review_allowed_roots_and_config_path(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    project = tmp_path / "repo"
    project.mkdir()
    (project / "app.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")
    config = project / "reviewagent.yml"
    config.write_text("rules: {}\n", encoding="utf-8")
    client = TestClient(dashboard_app_module.app)
    headers = {"Authorization": "Bearer dev-token"}

    ok = client.post(
        "/api/review/project",
        headers=headers,
        json={"project_path": str(project), "config_path": str(config), "enable_agents": True, "agents": "quality", "save_result": False},
    )
    assert ok.status_code == 200
    assert ok.json()["ok"] is True

    outside = client.post("/api/review/project", headers=headers, json={"project_path": str(Path.cwd()), "save_result": False})
    assert outside.json()["ok"] is False
    assert "outside" in outside.json()["error"]

    traversal = project / ".." / ".."
    assert client.post("/api/review/project", headers=headers, json={"project_path": str(traversal)}).json()["ok"] is False


def test_github_pr_url_and_network_guards(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    assert parse_github_pr_url("https://github.com/octo/repo/pull/7") == ("octo", "repo", 7)
    assert parse_github_pr_url("https://example.com/octo/repo/pull/7") is None
    service = HostedReviewService()

    blocked = service.review_github_pr("https://github.com/octo/repo/pull/7", {"allow_network": False})
    assert blocked.ok is False
    assert "allow_network" in blocked.error

    monkeypatch.setenv("GITHUB_TOKEN", "")
    missing = service.review_github_pr("https://github.com/octo/repo/pull/7", {"allow_network": True})
    assert missing.ok is False
    assert "GITHUB_TOKEN" in missing.error


def test_github_pr_mock_fetch_success(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert request.headers["Authorization"] == "Bearer secret-token"
        return httpx.Response(200, text=sample_diff())

    service = HostedReviewService(http_client=httpx.Client(transport=httpx.MockTransport(handler)))
    result = service.review_github_pr("https://github.com/octo/repo/pull/7", {"allow_network": True, "save_result": False})
    assert result.ok is True
    assert calls["count"] == 1


def test_review_api_auth_and_security(tmp_path: Path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)

    assert client.post("/api/review/diff", json={"diff_text": sample_diff()}).status_code == 401
    headers = {"Authorization": "Bearer dev-token"}
    response = client.post("/api/review/github-pr", headers=headers, json={"pr_url": "not-a-url"})
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert "dev-token" not in response.text


def test_allowed_path_helper_rejects_outside(tmp_path: Path) -> None:
    inside = tmp_path / "repo"
    inside.mkdir()
    assert ensure_allowed_path(str(inside), roots=[tmp_path]) == inside.resolve()
    try:
        ensure_allowed_path(str(Path.cwd()), roots=[tmp_path])
    except ValueError as exc:
        assert "outside" in str(exc)
    else:
        raise AssertionError("outside path should be rejected")
