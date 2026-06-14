import asyncio
from pathlib import Path

from magicreview.dashboard import app as dashboard_app_module
from magicreview.integrations.github.app import health as github_health
from magicreview.integrations.github.config import GitHubAppConfig


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
    assert ".magicreview" in dockerignore
    assert ".git" in dockerignore


def test_dockerfile_uses_python_slim_non_root_and_offline_default() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.12-slim" in dockerfile
    assert "USER magicreview" in dockerfile
    assert 'CMD ["mgreview", "--help"]' in dockerfile
    assert "MGREVIEW_DB_PATH=/data/magicreview.db" in dockerfile
    assert "EXPOSE 8080 8000" in dockerfile


def test_compose_defines_dashboard_github_app_and_mcp() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "dashboard:" in compose
    assert "github-app:" in compose
    assert "mcp:" in compose
    assert "MGREVIEW_LLM_PROVIDER: none" in compose
    assert "MGREVIEW_NETWORK_ENABLED" in compose
    assert "/health" in compose


def test_env_example_documents_offline_defaults() -> None:
    env_example = (ROOT / ".env.example").read_text(encoding="utf-8")

    assert "MGREVIEW_LLM_PROVIDER=none" in env_example
    assert "MGREVIEW_NETWORK_ENABLED=false" in env_example
    assert "MGREVIEW_ALLOW_LLM=false" in env_example
    assert "GITHUB_PRIVATE_KEY=" in env_example
    assert "Do not bake private keys into" in env_example


def test_dashboard_health_and_host_port_env(monkeypatch) -> None:
    monkeypatch.setenv("MGREVIEW_DASHBOARD_HOST", "0.0.0.0")
    monkeypatch.setenv("MGREVIEW_DASHBOARD_PORT", "9090")

    assert dashboard_app_module.health() == {"status": "ok", "service": "dashboard"}
    assert dashboard_app_module.dashboard_host_port() == ("0.0.0.0", 9090)


def test_github_health_and_host_port_env(monkeypatch) -> None:
    monkeypatch.setenv("MGREVIEW_GITHUB_HOST", "0.0.0.0")
    monkeypatch.setenv("MGREVIEW_GITHUB_PORT", "9000")

    assert asyncio.run(github_health()) == {"status": "ok", "service": "github-app"}
    config = GitHubAppConfig.from_env()
    assert config.host == "0.0.0.0"
    assert config.port == 9000


def test_packaged_entry_modules_import() -> None:
    import magicreview.cli.main
    import magicreview.dashboard.app
    import magicreview.integrations.github.app
    import magicreview.mcp_server.server

    assert callable(magicreview.cli.main.main)
    assert callable(magicreview.dashboard.app.main)
    assert callable(magicreview.integrations.github.app.main)
    assert callable(magicreview.mcp_server.server.main)
