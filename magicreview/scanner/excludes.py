"""Shared project-scan exclusion rules."""

from __future__ import annotations

from pathlib import Path


DEFAULT_EXCLUDED_DIRS = {
    ".coverage",
    ".eggs",
    ".egg-info",
    ".git",
    ".idea",
    ".magicreview",
    ".mypy_cache",
    ".pytest_acceptance",
    ".pytest_cache",
    ".pytest_tmp",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".venv_testpypi",
    ".venv_wheel_test",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "env",
    "htmlcov",
    "node_modules",
    "site-packages",
    "venv",
}


def should_exclude_path(path: Path, project_root: Path | None = None, *, excluded_dirs: set[str] | None = None) -> bool:
    """Return True when any path component should be skipped by project scans."""

    names = {name.casefold() for name in (excluded_dirs or DEFAULT_EXCLUDED_DIRS)}
    try:
        candidate = path.resolve() if project_root is None else path.resolve().relative_to(project_root.resolve())
    except (OSError, ValueError):
        candidate = path

    for part in candidate.parts:
        normalized = part.casefold()
        if normalized in names or normalized.endswith(".egg-info"):
            return True
    return False
