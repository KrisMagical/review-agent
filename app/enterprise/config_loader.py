"""Enterprise rule configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.models.issue import Issue


DEFAULT_CONFIG_NAMES = (
    "magicreview.yml",
    "magicreview.yaml",
    "magicreview.json",
    ".magicreview.yml",
    ".magicreview.yaml",
    ".magicreview.json",
)
VALID_SEVERITIES = {"critical", "high", "medium", "low"}


@dataclass
class EnterpriseRuleConfig:
    """Normalized enterprise rule configuration."""

    rules: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_path: Path | None = None
    errors: list[Issue] = field(default_factory=list)

    @property
    def has_rules(self) -> bool:
        return bool(self.rules)


class RuleConfigLoader:
    """Load YAML or JSON enterprise rule configuration."""

    max_config_size_bytes = 1024 * 1024

    def load(self, project_root: str | Path, config_path: str | Path | None = None) -> EnterpriseRuleConfig:
        root = Path(project_root).resolve()
        path = Path(config_path).expanduser().resolve() if config_path else self._find_default_config(root)
        if path is None or not path.exists():
            return EnterpriseRuleConfig()
        if not path.is_file():
            return EnterpriseRuleConfig(errors=[self._config_error(path, "Enterprise rule config path is not a file.")])
        try:
            if path.stat().st_size > self.max_config_size_bytes:
                return EnterpriseRuleConfig(source_path=path, errors=[self._config_error(path, "Enterprise rule config is too large.")])
            data = self._parse(path)
        except Exception:
            return EnterpriseRuleConfig(source_path=path, errors=[self._config_error(path, "Failed to load enterprise rule config.")])
        return self._normalize(data, path)

    @staticmethod
    def _find_default_config(root: Path) -> Path | None:
        for name in DEFAULT_CONFIG_NAMES:
            candidate = root / name
            if candidate.exists() and candidate.is_file():
                return candidate
        return None

    @staticmethod
    def _parse(path: Path) -> Any:
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            return {}
        suffix = path.suffix.lower()
        if suffix == ".json":
            return json.loads(text)
        if suffix in {".yml", ".yaml"}:
            import yaml

            return yaml.safe_load(text)
        raise ValueError("Unsupported enterprise config format.")

    def _normalize(self, data: Any, path: Path) -> EnterpriseRuleConfig:
        if data is None:
            return EnterpriseRuleConfig(source_path=path)
        if not isinstance(data, dict):
            return EnterpriseRuleConfig(source_path=path, errors=[self._config_error(path, "Enterprise rule config must be an object.")])
        raw_rules = data.get("rules", {})
        if raw_rules is None:
            raw_rules = {}
        if not isinstance(raw_rules, dict):
            return EnterpriseRuleConfig(source_path=path, errors=[self._config_error(path, "Enterprise rules must be an object.")])

        rules: dict[str, dict[str, Any]] = {}
        errors: list[Issue] = []
        for name, raw_rule in raw_rules.items():
            if not isinstance(name, str) or not isinstance(raw_rule, dict):
                errors.append(self._config_error(path, "Each enterprise rule must be an object."))
                continue
            normalized = dict(raw_rule)
            severity = str(normalized.get("severity", "medium")).lower()
            if severity not in VALID_SEVERITIES:
                errors.append(self._config_error(path, f"Invalid severity for enterprise rule '{name}'."))
                severity = "medium"
            normalized["severity"] = severity
            normalized["enabled"] = bool(normalized.get("enabled", False))
            rules[name] = normalized
        return EnterpriseRuleConfig(rules=rules, source_path=path, errors=errors)

    @staticmethod
    def _config_error(path: Path, message: str) -> Issue:
        return Issue(
            severity="low",
            type="EnterpriseRuleConfigError",
            file=str(path),
            line=1,
            message=message,
            suggestion="Fix the YAML or JSON syntax and validate rule fields.",
        )
