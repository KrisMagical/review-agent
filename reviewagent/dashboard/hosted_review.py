"""Hosted review helpers for Dashboard-triggered reviews."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from app.report.cli_formatters import normalize_result
from app.reviewer.service import ReviewService
from reviewagent.connected import NetworkPolicy
from reviewagent.dashboard.model_settings import ModelSettingsRepository
from reviewagent.integrations.github.client import GitHubAppClient
from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.repository_fetcher import GitHubRepositoryFetcher
from reviewagent.storage.repository import ReviewPersistenceService


GITHUB_PR_RE = re.compile(r"^https://github\.com/([^/]+)/([^/]+)/pull/(\d+)(?:/)?$")


@dataclass
class HostedReviewResponse:
    ok: bool
    result: dict[str, Any]
    review_run_id: int | None = None
    error: str = ""


def max_upload_bytes() -> int:
    try:
        return int(os.getenv("REVIEWAGENT_MAX_UPLOAD_BYTES", "5242880"))
    except ValueError:
        return 5 * 1024 * 1024


def allowed_review_roots() -> list[Path]:
    configured = os.getenv("REVIEWAGENT_ALLOWED_REVIEW_ROOTS", "")
    roots = [item.strip() for item in configured.split(",") if item.strip()]
    if not roots:
        roots = [str(Path.cwd())]
    return [Path(root).expanduser().resolve() for root in roots]


def ensure_allowed_path(path: str, *, roots: list[Path] | None = None) -> Path:
    resolved = Path(path).expanduser().resolve()
    allowed = roots or allowed_review_roots()
    if not any(_is_relative_to(resolved, root) for root in allowed):
        raise ValueError("Path is outside REVIEWAGENT_ALLOWED_REVIEW_ROOTS.")
    return resolved


def ensure_allowed_config_path(config_path: str | None, project_path: Path) -> str | None:
    if not config_path:
        return None
    resolved = ensure_allowed_path(config_path)
    if not _is_relative_to(resolved, project_path) and not any(_is_relative_to(resolved, root) for root in allowed_review_roots()):
        raise ValueError("Config path is outside the allowed review roots.")
    return str(resolved)


def network_policy_from_options(options: dict[str, Any], provider: str) -> NetworkPolicy:
    mode = str(options.get("code_sharing_mode") or "none").replace("-", "_")
    if mode not in {"none", "summary_only", "snippets", "full_context"}:
        mode = "none"
    return NetworkPolicy(
        enabled=_bool(options.get("allow_network")),
        allow_llm=_bool(options.get("allow_llm")),
        code_sharing_mode=mode,  # type: ignore[arg-type]
        allowed_providers=[provider] if provider and provider != "none" else [],
        audit_enabled=True,
    )


class HostedReviewService:
    def __init__(
        self,
        *,
        review_service: ReviewService | None = None,
        persistence: ReviewPersistenceService | None = None,
        model_settings: ModelSettingsRepository | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.review_service = review_service or ReviewService()
        self.persistence = persistence or ReviewPersistenceService()
        self.model_settings = model_settings or ModelSettingsRepository()
        self.http_client = http_client

    def review_diff(self, diff_text: str, options: dict[str, Any]) -> HostedReviewResponse:
        if not diff_text.strip():
            return self._error("Diff is required.")
        if len(diff_text.encode("utf-8")) > max_upload_bytes():
            return self._error("Diff exceeds the maximum upload size.")
        result = normalize_result(self.review_service.review_diff(diff_text))
        return self._maybe_save(result, "diff", "uploaded_diff", options)

    def review_project(self, project_path: str, options: dict[str, Any]) -> HostedReviewResponse:
        try:
            resolved = ensure_allowed_path(project_path)
            if not resolved.exists() or not resolved.is_dir():
                return self._error("Project path does not exist or is not a directory.")
            config_path = ensure_allowed_config_path(options.get("config_path") or None, resolved)
        except ValueError as exc:
            return self._error(str(exc))

        provider = self._provider(options)
        policy = network_policy_from_options(options, provider)
        result = normalize_result(
            self.review_service.review_project(
                str(resolved),
                enable_llm=_bool(options.get("enable_llm")),
                llm_provider=provider,
                config_path=config_path,
                enable_enterprise_rules=_bool(options.get("enable_enterprise_rules"), default=True),
                enable_agents=_bool(options.get("enable_agents")),
                agents=_agents(options.get("agents")),
                network_policy=policy,
            )
        )
        return self._maybe_save(result, "project", str(resolved), options)

    def review_github_pr(self, pr_url: str, options: dict[str, Any]) -> HostedReviewResponse:
        match = GITHUB_PR_RE.match(pr_url.strip())
        if not match:
            return self._error("Enter a valid GitHub pull request URL.")
        if not _bool(options.get("allow_network")):
            return self._error("GitHub PR review requires allow_network=true.")
        token = os.getenv("GITHUB_TOKEN", "")
        if not token:
            return self._error("GitHub PR review requires GITHUB_TOKEN or GitHub App configuration.")
        owner, repo, number = match.groups()
        try:
            mode = str(options.get("review_mode") or "diff_only")
            if mode == "full_project":
                return self._review_github_pr_full_project(owner, repo, int(number), pr_url, token, options)
            diff = self._fetch_github_diff(owner, repo, number, token)
        except Exception:
            return self._error("Failed to fetch GitHub PR diff.")
        result = normalize_result(self.review_service.review_diff(diff))
        return self._maybe_save(result, "github_pr", pr_url, options)

    def _review_github_pr_full_project(self, owner: str, repo: str, number: int, pr_url: str, token: str, options: dict[str, Any]) -> HostedReviewResponse:
        client = GitHubAppClient(app_id="", private_key="", token=token, http_client=self.http_client)
        try:
            pr = client.get_pull_request(owner, repo, number)
            head_sha = str(pr.get("head", {}).get("sha", ""))
            base_sha = str(pr.get("base", {}).get("sha", ""))
            fetcher = GitHubRepositoryFetcher(
                client,
                GitHubAppConfig(review_mode="full_project", enable_agents=_bool(options.get("enable_agents")), enable_llm=_bool(options.get("enable_llm"))),
            )
            workspace = fetcher.fetch_pull_request_project(owner, repo, head_sha)
        except Exception:
            return self._error("Failed to fetch GitHub project files for full_project review.")
        try:
            provider = self._provider(options)
            result = normalize_result(
                self.review_service.review_project(
                    str(workspace.root),
                    enable_llm=_bool(options.get("enable_llm")),
                    llm_provider=provider,
                    enable_enterprise_rules=_bool(options.get("enable_enterprise_rules"), default=True),
                    enable_agents=_bool(options.get("enable_agents")),
                    agents=_agents(options.get("agents")),
                    network_policy=network_policy_from_options(options, provider),
                )
            )
            result["issues"].extend(issue.to_dict() for issue in workspace.issues)
            options = {
                **options,
                "review_mode": "full_project",
                "owner": owner,
                "repo": repo,
                "pull_number": number,
                "head_sha": head_sha,
                "base_sha": base_sha,
                **workspace.metadata,
            }
            return self._maybe_save(result, "pull_request", f"{owner}/{repo}#{number}", options)
        finally:
            workspace.cleanup()

    def _fetch_github_diff(self, owner: str, repo: str, number: str, token: str) -> str:
        client = self.http_client or httpx.Client(timeout=30)
        response = client.get(
            f"https://api.github.com/repos/{owner}/{repo}/pulls/{number}",
            headers={
                "Accept": "application/vnd.github.v3.diff",
                "Authorization": f"Bearer {token}",
                "User-Agent": "ReviewAgent",
            },
        )
        response.raise_for_status()
        return response.text

    def _provider(self, options: dict[str, Any]) -> str:
        configured = self.model_settings.get()
        provider = str(options.get("llm_provider") or configured.provider or "none")
        return provider if provider else "none"

    def _maybe_save(self, result: dict[str, Any], target_type: str, target_ref: str, options: dict[str, Any]) -> HostedReviewResponse:
        review_run_id = None
        if _bool(options.get("save_result"), default=True):
            metadata = {
                "enable_llm": _bool(options.get("enable_llm")),
                "enable_agents": _bool(options.get("enable_agents")),
                "code_sharing_mode": options.get("code_sharing_mode", "none"),
                "provider": self._provider(options),
                "saved_from": "hosted_review_ui",
                "review_mode": options.get("review_mode", "diff_only"),
                "owner": options.get("owner"),
                "repo": options.get("repo"),
                "pull_number": options.get("pull_number"),
                "head_sha": options.get("head_sha"),
                "base_sha": options.get("base_sha"),
                "file_count": options.get("file_count"),
                "fetched_file_count": options.get("fetched_file_count"),
                "skipped_file_count": options.get("skipped_file_count"),
            }
            review_run_id = self.persistence.save_review_result(
                result,
                source="dashboard",
                target_type=target_type,
                target_ref=target_ref,
                metadata=metadata,
            )
        return HostedReviewResponse(ok=True, result=result, review_run_id=review_run_id)

    @staticmethod
    def _error(message: str) -> HostedReviewResponse:
        return HostedReviewResponse(ok=False, result={"issues": [], "summary": {"total": 0, "critical": 0, "high": 0, "medium": 0, "low": 0}}, error=message)


def parse_github_pr_url(url: str) -> tuple[str, str, int] | None:
    match = GITHUB_PR_RE.match(url.strip())
    if not match:
        return None
    owner, repo, number = match.groups()
    return owner, repo, int(number)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _agents(value: Any) -> list[str] | None:
    if not value:
        return None
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
