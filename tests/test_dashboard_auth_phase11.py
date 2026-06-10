import base64
import json
from pathlib import Path

from fastapi.testclient import TestClient

from reviewagent.dashboard import app as dashboard_app_module
from reviewagent.dashboard.auth import (
    is_valid_api_key,
    is_valid_login,
    load_auth_config,
    parse_basic_auth,
)
from reviewagent.storage.repository import ReviewPersistenceService


def configure_auth_env(monkeypatch, tmp_path: Path, *, basic: bool = False) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("REVIEWAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("REVIEWAGENT_SESSION_SECRET", "test-session-secret")
    monkeypatch.setenv("REVIEWAGENT_API_KEYS", "dev-token,second-token")
    monkeypatch.setenv("REVIEWAGENT_COOKIE_SECURE", "false")
    monkeypatch.setenv("REVIEWAGENT_BASIC_AUTH_ENABLED", "true" if basic else "false")


def test_auth_config_defaults_and_parsing(monkeypatch) -> None:
    for key in [
        "REVIEWAGENT_AUTH_ENABLED",
        "REVIEWAGENT_ADMIN_USERNAME",
        "REVIEWAGENT_ADMIN_PASSWORD",
        "REVIEWAGENT_SESSION_SECRET",
        "REVIEWAGENT_API_KEYS",
        "REVIEWAGENT_COOKIE_SECURE",
    ]:
        monkeypatch.delenv(key, raising=False)

    default = load_auth_config()
    assert default.enabled is False
    assert default.admin_username == "admin"
    assert default.api_keys == ()

    monkeypatch.setenv("REVIEWAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("REVIEWAGENT_API_KEYS", "a, b ,, c")
    monkeypatch.setenv("REVIEWAGENT_COOKIE_SECURE", "true")
    configured = load_auth_config()
    assert configured.enabled is True
    assert configured.api_keys == ("a", "b", "c")
    assert configured.cookie_secure is True


def test_compare_digest_login_and_api_key(monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("REVIEWAGENT_API_KEYS", "dev-token")

    assert is_valid_login("admin", "password")
    assert not is_valid_login("admin", "wrong")
    assert is_valid_api_key("dev-token")
    assert not is_valid_api_key("bad-token")


def test_dashboard_auth_disabled_allows_pages_and_api(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "disabled.db"))
    monkeypatch.setenv("REVIEWAGENT_AUTH_ENABLED", "false")
    client = TestClient(dashboard_app_module.app)

    assert client.get("/dashboard").status_code == 200
    assert client.get("/api/stats/overview").status_code == 200
    assert client.get("/health").status_code == 200


def test_dashboard_login_logout_flow(tmp_path: Path, monkeypatch) -> None:
    configure_auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)

    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")

    assert client.get("/login").status_code == 200
    failed = client.post(
        "/login",
        data={"username": "admin", "password": "wrong", "next": "/dashboard"},
        follow_redirects=False,
    )
    assert failed.status_code == 401
    assert "wrong" not in failed.text
    assert "test-session-secret" not in failed.text

    successful = client.post(
        "/login",
        data={"username": "admin", "password": "password", "next": "/dashboard"},
        follow_redirects=False,
    )
    assert successful.status_code == 303
    assert successful.headers["location"] == "/dashboard"
    assert client.get("/dashboard").status_code == 200

    logout = client.get("/logout", follow_redirects=False)
    assert logout.status_code == 303
    assert client.get("/dashboard", follow_redirects=False).status_code == 303


def test_dashboard_api_bearer_and_session_auth(tmp_path: Path, monkeypatch) -> None:
    configure_auth_env(monkeypatch, tmp_path)
    ReviewPersistenceService(tmp_path / "auth.db").save_review_result({"issues": []}, source="cli", target_type="project", target_ref=".")
    client = TestClient(dashboard_app_module.app)

    unauthorized = client.get("/api/stats/overview")
    assert unauthorized.status_code == 401
    assert unauthorized.json() == {"detail": "Authentication required"}

    assert client.get("/api/stats/overview", headers={"Authorization": "Bearer bad"}).status_code == 401
    assert client.get("/api/stats/overview", headers={"Authorization": "Bearer dev-token"}).status_code == 200

    client.post("/login", data={"username": "admin", "password": "password", "next": "/dashboard"})
    assert client.get("/api/stats/overview").status_code == 200


def test_dashboard_basic_auth_when_enabled(tmp_path: Path, monkeypatch) -> None:
    configure_auth_env(monkeypatch, tmp_path, basic=True)
    client = TestClient(dashboard_app_module.app)
    good = base64.b64encode(b"admin:password").decode("ascii")
    bad = base64.b64encode(b"admin:wrong").decode("ascii")

    assert parse_basic_auth(f"Basic {good}") == ("admin", "password")
    assert client.get("/api/stats/overview", headers={"Authorization": f"Basic {good}"}).status_code == 200
    assert client.get("/api/stats/overview", headers={"Authorization": f"Basic {bad}"}).status_code == 401


def test_auth_responses_do_not_expose_secrets(tmp_path: Path, monkeypatch) -> None:
    configure_auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)

    body = client.get("/login").text + client.get("/api/stats/overview").text
    assert "test-session-secret" not in body
    assert "dev-token" not in body
    assert "password" not in json.dumps(client.get("/api/stats/overview").json()).lower()
