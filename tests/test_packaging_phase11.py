import json
import subprocess
import sys
from importlib import resources
from pathlib import Path

import magicreview
from magicreview.config.env import get_env
from magicreview.storage.database import default_db_path


def run_module_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", *args],
        capture_output=True,
        text=True,
    )


def test_package_version_is_available() -> None:
    assert magicreview.__version__ == "0.1.1"


def test_cli_version_uses_package_version() -> None:
    result = run_module_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == f"MagicReview {magicreview.__version__}"


def test_cli_help_entry_points_are_importable() -> None:
    for args in [("--help",), ("file", "--help"), ("diff", "--help"), ("project", "--help")]:
        result = run_module_cli(*args)
        assert result.returncode == 0
        assert "usage:" in result.stdout


def test_packaging_public_modules_import() -> None:
    import magicreview.cli.main
    import magicreview.dashboard.app
    import magicreview.integrations.github.app
    import magicreview.mcp_server.server

    assert callable(magicreview.cli.main.main)
    assert callable(magicreview.dashboard.app.main)
    assert callable(magicreview.integrations.github.app.main)
    assert callable(magicreview.mcp_server.server.main)


def test_runtime_package_data_is_accessible() -> None:
    dashboard_template = resources.files("magicreview.dashboard").joinpath("templates/index.html")
    prompt_template = resources.files("app.llm").joinpath("prompts/architecture_review.md")

    assert dashboard_template.is_file()
    assert prompt_template.is_file()
    assert "{% extends" in dashboard_template.read_text(encoding="utf-8")
    assert "JSON" in prompt_template.read_text(encoding="utf-8")


def test_default_project_review_is_offline_and_json(tmp_path) -> None:
    (tmp_path / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")

    result = run_module_cli("project", str(tmp_path), "--format", "json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert "issues" in payload
    assert all(issue["type"] != "ArchitectureReviewError" for issue in payload["issues"])


def test_mgreview_env_prefix_is_read(monkeypatch) -> None:
    monkeypatch.delenv("MGREVIEW_DB_PATH", raising=False)
    monkeypatch.setenv("MGREVIEW_DB_PATH", "new.db")

    assert get_env("DB_PATH") == "new.db"


def test_reviewagent_env_prefix_is_ignored(monkeypatch) -> None:
    monkeypatch.setenv("REVIEWAGENT_DB_PATH", "legacy.db")
    monkeypatch.delenv("MGREVIEW_DB_PATH", raising=False)

    assert get_env("DB_PATH", "default.db") == "default.db"


def test_default_magicreview_data_path_only(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MGREVIEW_DB_PATH", raising=False)

    assert default_db_path() == Path(".magicreview") / "magicreview.db"

    legacy = Path(".reviewagent") / "reviewagent.db"
    legacy.parent.mkdir()
    legacy.write_text("", encoding="utf-8")

    assert default_db_path() == Path(".magicreview") / "magicreview.db"
