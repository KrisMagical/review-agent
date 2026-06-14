"""Project Python file scanner."""

from __future__ import annotations

import os
from pathlib import Path

from magicreview.scanner import DEFAULT_EXCLUDED_DIRS, should_exclude_path

DEFAULT_EXCLUDE_DIRS = DEFAULT_EXCLUDED_DIRS


class ProjectScanner:
    """Discover Python files under a project root."""

    def __init__(self, exclude_dirs: set[str] | None = None) -> None:
        self.exclude_dirs = set(exclude_dirs or DEFAULT_EXCLUDE_DIRS)

    def scan(self, root: Path) -> list[Path]:
        """Return stable project-relative Python file paths."""

        project_root = root.resolve()
        if project_root.is_file():
            return [Path(project_root.name)] if project_root.suffix == ".py" else []

        files: list[Path] = []
        for current_root, dirnames, filenames in os.walk(project_root, topdown=True, followlinks=False):
            current_path = Path(current_root)
            if should_exclude_path(current_path, project_root, excluded_dirs=self.exclude_dirs):
                dirnames[:] = []
                continue

            dirnames[:] = [
                dirname
                for dirname in dirnames
                if not should_exclude_path(current_path / dirname, project_root, excluded_dirs=self.exclude_dirs)
            ]

            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = current_path / filename
                if should_exclude_path(path, project_root, excluded_dirs=self.exclude_dirs):
                    continue
                try:
                    relative = path.resolve().relative_to(project_root)
                except (OSError, ValueError):
                    continue
                files.append(relative)
        return sorted(files, key=lambda item: item.as_posix())
