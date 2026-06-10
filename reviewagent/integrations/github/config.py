"""GitHub App environment configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _review_mode(value: str | None) -> Literal["diff_only", "full_project"]:
    return "full_project" if (value or "").strip().lower() == "full_project" else "diff_only"


@dataclass(frozen=True)
class GitHubAppConfig:
    app_id: str = ""
    private_key: str = ""
    webhook_secret: str = ""
    app_name: str = "ReviewAgent"
    enable_inline_comments: bool = True
    enable_summary_comment: bool = True
    enable_agents: bool = False
    enable_llm: bool = False
    save_results: bool = False
    review_mode: str = "diff_only"
    config_path: str | None = None
    max_inline_comments: int = 30
    fail_on: str | None = None
    host: str = "0.0.0.0"
    port: int = 8000
    allow_network: bool = False
    allow_llm: bool = False
    code_sharing_mode: str = "none"
    max_project_files: int = 2000
    max_file_bytes: int = 2 * 1024 * 1024
    max_project_bytes: int = 50 * 1024 * 1024
    fetch_timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "GitHubAppConfig":
        return cls(
            app_id=os.getenv("GITHUB_APP_ID", ""),
            private_key=os.getenv("GITHUB_PRIVATE_KEY", ""),
            webhook_secret=os.getenv("GITHUB_WEBHOOK_SECRET", ""),
            app_name=os.getenv("GITHUB_APP_NAME", "ReviewAgent"),
            enable_inline_comments=_bool_env("REVIEWAGENT_GITHUB_ENABLE_INLINE_COMMENTS", True),
            enable_summary_comment=_bool_env("REVIEWAGENT_GITHUB_ENABLE_SUMMARY_COMMENT", True),
            enable_agents=_bool_env("REVIEWAGENT_GITHUB_ENABLE_AGENTS", False),
            enable_llm=_bool_env("REVIEWAGENT_GITHUB_ENABLE_LLM", False),
            save_results=_bool_env("REVIEWAGENT_GITHUB_SAVE_RESULTS", False),
            review_mode=_review_mode(os.getenv("REVIEWAGENT_GITHUB_REVIEW_MODE", "diff_only")),
            config_path=os.getenv("REVIEWAGENT_GITHUB_CONFIG_PATH") or None,
            max_inline_comments=_int_env("REVIEWAGENT_GITHUB_MAX_INLINE_COMMENTS", 30),
            fail_on=os.getenv("REVIEWAGENT_GITHUB_FAIL_ON") or None,
            host=os.getenv("REVIEWAGENT_GITHUB_HOST", "0.0.0.0"),
            port=_int_env("REVIEWAGENT_GITHUB_PORT", 8000),
            allow_network=_bool_env("REVIEWAGENT_GITHUB_ALLOW_NETWORK", False),
            allow_llm=_bool_env("REVIEWAGENT_GITHUB_ALLOW_LLM", False),
            code_sharing_mode=os.getenv("REVIEWAGENT_GITHUB_CODE_SHARING_MODE", "none").replace("-", "_"),
            max_project_files=_int_env("REVIEWAGENT_GITHUB_MAX_PROJECT_FILES", 2000),
            max_file_bytes=_int_env("REVIEWAGENT_GITHUB_MAX_FILE_BYTES", 2 * 1024 * 1024),
            max_project_bytes=_int_env("REVIEWAGENT_GITHUB_MAX_PROJECT_BYTES", 50 * 1024 * 1024),
            fetch_timeout_seconds=_int_env("REVIEWAGENT_GITHUB_FETCH_TIMEOUT_SECONDS", 30),
        )

    def validate_for_webhook(self) -> list[str]:
        missing = []
        if not self.webhook_secret:
            missing.append("GITHUB_WEBHOOK_SECRET")
        if not self.app_id:
            missing.append("GITHUB_APP_ID")
        if not self.private_key:
            missing.append("GITHUB_PRIVATE_KEY")
        return missing
