import httpx
from fastapi.testclient import TestClient

from reviewagent.dashboard import app as dashboard_app_module
from reviewagent.dashboard.model_settings import (
    ModelProviderTester,
    ModelSettingsRepository,
    mask_api_key,
)


def auth_env(monkeypatch, tmp_path):
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "models.db"))
    monkeypatch.setenv("REVIEWAGENT_AUTH_ENABLED", "true")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("REVIEWAGENT_ADMIN_PASSWORD", "password")
    monkeypatch.setenv("REVIEWAGENT_SESSION_SECRET", "test-secret")
    monkeypatch.setenv("REVIEWAGENT_API_KEYS", "dev-token")


def test_model_settings_repository_defaults_save_mask_clear_and_env_priority(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "repo.db"))
    repo = ModelSettingsRepository()

    default = repo.get()
    assert default.provider == "none"
    assert default.to_safe_dict()["api_key_masked"] is None

    saved = repo.save(
        {
            "provider": "openai",
            "enabled": True,
            "model": "gpt-4o-mini",
            "api_key": "sk-test1234abcd",
            "code_sharing_mode": "summary_only",
            "allow_network": True,
            "allow_llm": True,
        }
    )
    safe = saved.to_safe_dict()
    assert safe["provider"] == "openai"
    assert safe["api_key_source"] == "stored"
    assert safe["api_key_masked"] == "sk-****abcd"
    assert "sk-test1234abcd" not in str(safe)

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env9999zzzz")
    from_env = repo.get().to_safe_dict()
    assert from_env["api_key_source"] == "env"
    assert from_env["api_key_masked"] == "sk-****zzzz"

    monkeypatch.delenv("OPENAI_API_KEY")
    cleared = repo.clear_api_key().to_safe_dict()
    assert cleared["api_key_source"] == "none"
    assert cleared["api_key_masked"] is None


def test_model_settings_repository_supports_anthropic_and_ollama(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "providers.db"))
    repo = ModelSettingsRepository()

    anthropic = repo.save({"provider": "anthropic", "enabled": True, "api_key": "anthropic-secret"})
    assert anthropic.provider == "anthropic"
    assert anthropic.to_safe_dict()["api_key_masked"] == "****cret"

    ollama = repo.save({"provider": "ollama", "enabled": True, "base_url": "http://localhost:11434", "model": "llama3"})
    assert ollama.provider == "ollama"
    assert ollama.base_url == "http://localhost:11434"


def test_model_settings_page_requires_auth_and_masks_secret(tmp_path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    repo = ModelSettingsRepository()
    repo.save({"provider": "openai", "enabled": True, "api_key": "sk-secret0000abcd", "code_sharing_mode": "full_context"})
    client = TestClient(dashboard_app_module.app)

    redirect = client.get("/settings/models", follow_redirects=False)
    assert redirect.status_code == 303
    assert redirect.headers["location"].startswith("/login")

    client.post("/login", data={"username": "admin", "password": "password", "next": "/settings/models"})
    page = client.get("/settings/models")
    assert page.status_code == 200
    assert "openai" in page.text
    assert "full_context" in page.text
    assert "sk-****abcd" in page.text
    assert "sk-secret0000abcd" not in page.text
    assert "may send source code context" in page.text


def test_model_settings_api_auth_save_test_and_clear(tmp_path, monkeypatch) -> None:
    auth_env(monkeypatch, tmp_path)
    client = TestClient(dashboard_app_module.app)

    assert client.get("/api/settings/models").status_code == 401
    headers = {"Authorization": "Bearer dev-token"}
    assert client.get("/api/settings/models", headers=headers).status_code == 200

    saved = client.post(
        "/api/settings/models",
        headers=headers,
        json={"provider": "mock", "enabled": True, "model": "mock-model", "code_sharing_mode": "summary_only"},
    )
    assert saved.status_code == 200
    assert saved.json()["provider"] == "mock"

    tested = client.post("/api/settings/models/test", headers=headers, json={})
    assert tested.status_code == 200
    assert tested.json()["ok"] is True

    cleared = client.delete("/api/settings/models/api-key", headers=headers)
    assert cleared.status_code == 200
    assert "api_key_value" not in cleared.text


def test_provider_test_respects_network_policy_and_uses_mocked_http(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", str(tmp_path / "test.db"))
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        assert b"Reply with OK." in request.content
        assert b"project" not in request.content.lower()
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    tester = ModelProviderTester(http_client=client)
    repo = ModelSettingsRepository()

    blocked = repo.save(
        {
            "provider": "openai",
            "enabled": True,
            "api_key": "sk-secret0000abcd",
            "code_sharing_mode": "none",
            "allow_network": False,
            "allow_llm": False,
        }
    )
    assert tester.test(blocked)["ok"] is False
    assert calls["count"] == 0

    allowed = repo.save(
        {
            "provider": "openai",
            "enabled": True,
            "api_key": "sk-secret0000abcd",
            "code_sharing_mode": "summary_only",
            "allow_network": True,
            "allow_llm": True,
        }
    )
    assert tester.test(allowed)["ok"] is True
    assert calls["count"] == 1


def test_none_and_mask_helpers() -> None:
    assert mask_api_key("") is None
    assert mask_api_key("short") == "****"
    assert ModelProviderTester().test(ModelSettingsRepository().get())["ok"] is False
