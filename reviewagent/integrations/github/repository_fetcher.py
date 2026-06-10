"""Fetch GitHub repository files into a temporary project workspace."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from app.models.issue import Issue
from reviewagent.integrations.github.client import GitHubAppClient, GitHubClientError
from reviewagent.integrations.github.config import GitHubAppConfig


ALLOWED_FILENAMES = {
    "reviewagent.yml",
    "reviewagent.yaml",
    "reviewagent.json",
    ".reviewagent.yml",
    ".reviewagent.yaml",
    ".reviewagent.json",
    "pyproject.toml",
    "README.md",
}
IGNORED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "node_modules",
    "dist",
    "build",
    ".tox",
    ".eggs",
}
SECRET_NAMES = {".env", ".env.local", "id_rsa", "id_ed25519"}


@dataclass
class GitHubProjectWorkspace:
    temp: TemporaryDirectory[str]
    root: Path
    metadata: dict[str, Any]
    issues: list[Issue]

    def cleanup(self) -> None:
        self.temp.cleanup()


class GitHubRepositoryFetcher:
    def __init__(self, client: GitHubAppClient, config: GitHubAppConfig) -> None:
        self.client = client
        self.config = config

    def fetch_pull_request_project(self, owner: str, repo: str, head_sha: str) -> GitHubProjectWorkspace:
        temp = TemporaryDirectory(prefix="reviewagent-gh-")
        root = Path(temp.name)
        issues: list[Issue] = []
        metadata: dict[str, Any] = {"file_count": 0, "fetched_file_count": 0, "skipped_file_count": 0}
        try:
            tree = self.client.get_repository_file_tree_for_ref(owner, repo, head_sha)
            entries = list(tree.get("tree", []))
            metadata["file_count"] = len(entries)
            total_bytes = 0
            fetched = 0
            skipped = 0
            for entry in entries:
                if entry.get("type") != "blob":
                    continue
                path = str(entry.get("path", ""))
                if not self._should_fetch(path):
                    skipped += 1
                    continue
                if fetched >= self.config.max_project_files:
                    issues.append(self._issue("Project file count exceeds configured limit."))
                    break
                size = int(entry.get("size") or 0)
                if size > self.config.max_file_bytes:
                    skipped += 1
                    issues.append(self._issue(f"Skipped oversized file: {path}", file=path))
                    continue
                if total_bytes + size > self.config.max_project_bytes:
                    issues.append(self._issue("Project byte size exceeds configured limit."))
                    break
                blob_sha = str(entry.get("sha", ""))
                content = self.client.get_blob_text(owner, repo, blob_sha)
                if len(content.encode("utf-8")) > self.config.max_file_bytes:
                    skipped += 1
                    issues.append(self._issue(f"Skipped oversized file: {path}", file=path))
                    continue
                target = self._safe_target(root, path)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
                fetched += 1
                total_bytes += len(content.encode("utf-8"))
            metadata.update({"fetched_file_count": fetched, "skipped_file_count": skipped, "fetched_bytes": total_bytes})
            return GitHubProjectWorkspace(temp=temp, root=root, metadata=metadata, issues=issues)
        except Exception:
            temp.cleanup()
            raise

    def _should_fetch(self, path: str) -> bool:
        parts = Path(path).parts
        if ".." in parts or Path(path).is_absolute():
            raise GitHubClientError("Unsafe repository path encountered.")
        if any(part in IGNORED_PARTS for part in parts):
            return False
        name = Path(path).name
        lowered = name.lower()
        if lowered in SECRET_NAMES or "private_key" in lowered or lowered.endswith(".pem"):
            return False
        return path.endswith(".py") or name in ALLOWED_FILENAMES

    @staticmethod
    def _safe_target(root: Path, path: str) -> Path:
        target = (root / path).resolve()
        try:
            target.relative_to(root.resolve())
        except ValueError as exc:
            raise GitHubClientError("Unsafe repository path encountered.") from exc
        return target

    @staticmethod
    def _issue(message: str, *, file: str = "") -> Issue:
        return Issue(
            severity="low",
            type="GitHubProjectFetchError",
            file=file,
            line=1,
            message=message,
            suggestion="Check GitHub permissions, repository size, and review mode configuration.",
        )
