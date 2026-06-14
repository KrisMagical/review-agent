import json
import subprocess
import sys
from pathlib import Path

from app.reviewer import ReviewService
from magicreview.mcp_server import tools


def write_policy_project(root: Path) -> Path:
    config = root / "magicreview.yml"
    config.write_text(
        """
rules:
  no_select_star:
    enabled: true
    severity: high
  max_parameters:
    enabled: true
    max_params: 2
    severity: medium
""",
        encoding="utf-8",
    )
    (root / "app").mkdir()
    (root / "app" / "services").mkdir()
    (root / "app" / "main.py").write_text(
        "def run(cursor, a, b):\n    cursor.execute('SELECT * FROM users')\n    return a\n",
        encoding="utf-8",
    )
    (root / "app" / "services" / "user_service.py").write_text("class UserService:\n    pass\n", encoding="utf-8")
    return config


def test_review_project_auto_loads_config_and_can_disable(tmp_path: Path) -> None:
    write_policy_project(tmp_path)

    enabled = ReviewService().review_project(str(tmp_path))
    disabled = ReviewService().review_project(str(tmp_path), enable_enterprise_rules=False)

    assert "EnterpriseNoSelectStar" in {issue["type"] for issue in enabled["issues"]}
    assert not any(issue["type"].startswith("Enterprise") for issue in disabled["issues"])


def test_review_project_explicit_config_and_config_error_do_not_block_static(tmp_path: Path) -> None:
    config = write_policy_project(tmp_path)
    explicit = ReviewService().review_project(str(tmp_path), config_path=str(config))
    assert "EnterpriseMaxParameters" in {issue["type"] for issue in explicit["issues"]}

    config.write_text("rules: [", encoding="utf-8")
    result = ReviewService().review_project(str(tmp_path), config_path=str(config))
    types = {issue["type"] for issue in result["issues"]}
    assert "EnterpriseRuleConfigError" in types
    assert "TypeHintRule" in types


def test_review_file_supports_explicit_config(tmp_path: Path) -> None:
    config = write_policy_project(tmp_path)
    result = ReviewService().review_file(str(tmp_path / "app" / "main.py"), config_path=str(config))

    assert "EnterpriseNoSelectStar" in {issue["type"] for issue in result["issues"]}


def test_cli_project_config_and_no_enterprise(tmp_path: Path) -> None:
    config = write_policy_project(tmp_path)
    enabled = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path), "--config", str(config)],
        check=True,
        capture_output=True,
        text=True,
    )
    disabled = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path), "--no-enterprise"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "EnterpriseNoSelectStar" in {issue["type"] for issue in json.loads(enabled.stdout)["issues"]}
    assert not any(issue["type"].startswith("Enterprise") for issue in json.loads(disabled.stdout)["issues"])


def test_mcp_project_enterprise_params_and_llm_can_coexist(tmp_path: Path) -> None:
    config = write_policy_project(tmp_path)
    result = tools.review_project(str(tmp_path), config_path=str(config), enable_llm=True, llm_provider="mock")
    disabled = tools.review_project(str(tmp_path), config_path=str(config), enable_enterprise_rules=False)

    types = {issue["type"] for issue in result["issues"]}
    assert "EnterpriseNoSelectStar" in types
    assert "MaintainabilityRisk" in types
    assert not any(issue["type"].startswith("Enterprise") for issue in disabled["issues"])
