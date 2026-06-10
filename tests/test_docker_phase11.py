import asyncio
from pathlib import Path

from reviewagent.dashboard import app as dashboard_app_module
from reviewagent.integrations.github.app import health as github_health
from reviewagent.integrations.github.config import GitHubAppConfig


ROOT = Path(__file__).resolve().parents[1]


def test_docker_files_exist_and_protect_secrets() -> None:
    for relative_path in [
        "Dockerfile",
        "docker-compose.yml",
        ".dockerignore",
        ".env.example",
        "docker/README.md",
        ".github/workflows/docker.yml",
    ]:
        assert (ROOT / relative_path).is_file()

    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert ".env" in dockerignore
    assert ".reviewagent" in dockerignore
    assert ".git" in dockerignore


def test_dockerfile_uses_python_slim_non_root_and_offline_default() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "USER reviewagent" in dockerfile
    assert 'CMD ["review", "--help"]' in dockerfile
    assert "REVIEWAGENT_DB_PATH=/data/reviewagent.db" in dockerfile
    assert "EXPOSE 8080 8000" in dockerfile


def test_compose_defines_dashboard_github_app_and_mcp() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "dashboard:" in compose
    assert "github-app:" in compose
    assert "mcp:" in compose
    assert "REVIEWAGENT_LLM_PROVIDER: none" in compose
    assert "REVIEWAGENT_NETWORK_ENABLED" in compose
    assert "/health" in compose


def test_env_example_documents_offline_defaults() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "REVIEWAGENT_LLM_PROVIDER=none" in env_example
    assert "REVIEWAGENT_NETWORK_ENABLED=false" in env_example
    assert "REVIEWAGENT_ALLOW_LLM=false" in env_example
    assert "GITHUB_PRIVATE_KEY=" in env_example
    assert "Do not bake private keys into" in env_example


def test_dashboard_health_and_host_port_env(monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("REVIEWAGENT_DASHBOARD_PORT", "9090")

    assert dashboard_app_module.health() == {"status": "ok", "service": "dashboard"}
    assert dashboard_app_module.dashboard_host_port() == ("0.0.0.0", 9090)


def test_github_health_and_host_port_env(monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_GITHUB_HOST", "0.0.0.0")
    monkeypatch.setenv("REVIEWAGENT_GITHUB_PORT", "9000")

    assert asyncio.run(github_health()) == {"status": "ok", "service": "github-app"}
    config = GitHubAppConfig.from_env()
    assert config.host == "0.0.0.0"
    assert config.port == 9000


def test_packaged_entry_modules_import() -> None:
    import reviewagent.cli.main
    import reviewagent.dashboard.app
    import reviewagent.integrations.github.app
    import reviewagent.mcp_server.server

    assert callable(reviewagent.cli.main.main)
    assert callable(reviewagent.dashboard.app.main)
    assert callable(reviewagent.integrations.github.app.main)
    assert callable(reviewagent.mcp_server.server.main)
