import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.project.scanner import ProjectScanner
from app.reviewer import ReviewService


def write(path: Path, source: str = "def run(x):\n    return 10 / x\n") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def issue_files(result: dict) -> set[str]:
    return {str(issue.get("file", "")).replace("\\", "/") for issue in result.get("issues", [])}


def issue_types(result: dict) -> set[str]:
    return {str(issue.get("type", "")) for issue in result.get("issues", [])}


def test_project_review_skips_virtualenv_and_site_packages(tmp_path: Path) -> None:
    write(tmp_path / ".venv_testpypi" / "Lib" / "site-packages" / "fakepkg" / "deeply_nested.py")
    write(tmp_path / "sample_project" / "app.py")
    write(tmp_path / "bad_code.py")

    result = ReviewService().review_project(str(tmp_path))
    files = issue_files(result)

    assert all(".venv_testpypi" not in file for file in files)
    assert all("site-packages" not in file for file in files)
    assert any(file.endswith("bad_code.py") or file.endswith("sample_project/app.py") for file in files)
    assert issue_types(result) & {"ZeroDivisionRule", "TypeHintRule"}
    assert "maximum recursion depth exceeded" not in json.dumps(result)


def test_project_review_skips_common_dependency_cache_and_build_dirs(tmp_path: Path) -> None:
    excluded_dirs = [
        ".magicreview",
        ".mypy_cache",
        ".pytest_cache",
        ".pytest_tmp",
        ".ruff_cache",
        ".tox",
        ".eggs",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "env",
        "htmlcov",
        "node_modules",
        "site-packages",
        "venv",
    ]
    for dirname in excluded_dirs:
        write(tmp_path / dirname / "ignored.py")
    write(tmp_path / "app.py")

    result = ReviewService().review_project(str(tmp_path))
    files = issue_files(result)

    for dirname in excluded_dirs:
        assert all(dirname not in file for file in files)
    assert any(file.endswith("app.py") for file in files)
    assert issue_types(result) & {"ZeroDivisionRule", "TypeHintRule"}


def test_cli_project_review_with_virtualenv_root_outputs_json(tmp_path: Path) -> None:
    write(tmp_path / ".venv_testpypi" / "Lib" / "site-packages" / "pkg" / "module.py")
    write(tmp_path / "bad_code.py")

    result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path), "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    rendered = json.dumps(payload)

    assert "maximum recursion depth exceeded" not in rendered
    assert all(".venv_testpypi" not in file for file in issue_files(payload))
    assert all("site-packages" not in file for file in issue_files(payload))
    assert issue_types(payload) & {"ZeroDivisionRule", "TypeHintRule"}


def test_project_scanner_does_not_follow_symlink_cycles(tmp_path: Path) -> None:
    write(tmp_path / "app.py")
    loop = tmp_path / "loop"
    try:
        os.symlink(tmp_path, loop, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink creation is not available: {exc}")

    result = ProjectScanner().scan(tmp_path)

    assert result == [Path("app.py")]
