import json
from pathlib import Path

from app.enterprise import RuleConfigLoader


def test_config_loader_discovers_yaml_and_json(tmp_path: Path) -> None:
    (tmp_path / "magicreview.yml").write_text("rules:\n  no_select_star:\n    enabled: true\n    severity: high\n", encoding="utf-8")
    config = RuleConfigLoader().load(tmp_path)
    assert config.rules["no_select_star"]["enabled"] is True

    (tmp_path / "magicreview.yml").unlink()
    (tmp_path / "magicreview.json").write_text(json.dumps({"rules": {"max_parameters": {"enabled": True, "max_params": 2}}}), encoding="utf-8")
    config = RuleConfigLoader().load(tmp_path)
    assert config.rules["max_parameters"]["max_params"] == 2


def test_config_loader_explicit_path_takes_priority(tmp_path: Path) -> None:
    (tmp_path / "magicreview.yml").write_text("rules:\n  no_select_star:\n    enabled: true\n", encoding="utf-8")
    explicit = tmp_path / "custom.json"
    explicit.write_text(json.dumps({"rules": {"forbidden_imports": {"enabled": True, "imports": ["os.system"]}}}), encoding="utf-8")

    config = RuleConfigLoader().load(tmp_path, explicit)

    assert "forbidden_imports" in config.rules
    assert "no_select_star" not in config.rules


def test_config_loader_missing_file_is_not_error(tmp_path: Path) -> None:
    config = RuleConfigLoader().load(tmp_path, tmp_path / "missing.yml")

    assert config.rules == {}
    assert config.errors == []


def test_config_loader_reports_yaml_syntax_and_invalid_severity(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "magicreview.yml"
    bad_yaml.write_text("rules: [", encoding="utf-8")
    assert RuleConfigLoader().load(tmp_path).errors[0].type == "EnterpriseRuleConfigError"

    bad_yaml.write_text("rules:\n  no_select_star:\n    enabled: true\n    severity: urgent\n", encoding="utf-8")
    config = RuleConfigLoader().load(tmp_path)
    assert config.errors[0].type == "EnterpriseRuleConfigError"
    assert config.rules["no_select_star"]["severity"] == "medium"


def test_config_loader_uses_yaml_safe_load(tmp_path: Path) -> None:
    config_file = tmp_path / "magicreview.yml"
    config_file.write_text("!!python/object/apply:os.system ['echo unsafe']", encoding="utf-8")

    config = RuleConfigLoader().load(tmp_path)

    assert config.errors
    assert config.errors[0].type == "EnterpriseRuleConfigError"
