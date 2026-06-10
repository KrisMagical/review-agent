import json
import subprocess
import sys
from importlib import resources

import reviewagent


def run_module_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "reviewagent.cli.main", *args],
        capture_output=True,
        text=True,
    )


def test_package_version_is_available() -> None:
    assert reviewagent.__version__ == "0.1.0"


def test_cli_version_uses_package_version() -> None:
    result = run_module_cli("--version")

    assert result.returncode == 0
    assert result.stdout.strip() == f"ReviewAgent {reviewagent.__version__}"


def test_cli_help_entry_points_are_importable() -> None:
    for args in [("--help",), ("file", "--help"), ("diff", "--help"), ("project", "--help")]:
        result = run_module_cli(*args)
        assert result.returncode == 0
        assert "usage:" in result.stdout


def test_packaging_public_modules_import() -> None:
    import reviewagent.cli.main
    import reviewagent.dashboard.app
    import reviewagent.integrations.github.app
    import reviewagent.mcp_server.server

    assert callable(reviewagent.cli.main.main)
    assert callable(reviewagent.dashboard.app.main)
    assert callable(reviewagent.integrations.github.app.main)
    assert callable(reviewagent.mcp_server.server.main)


def test_runtime_package_data_is_accessible() -> None:
    dashboard_template = resources.files("reviewagent.dashboard").joinpath("templates/index.html")
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
