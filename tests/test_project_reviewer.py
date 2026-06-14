import json
import subprocess
import sys
from pathlib import Path

from app.models.issue import Issue
from app.reviewer import ProjectReviewer


class FakeRuff:
    def check_project(self, _root):
        return [
            Issue(
                severity="low",
                type="RuffUnusedImport",
                file="pkg/a.py",
                line=1,
                message="F401: unused import",
                suggestion="Remove unused imports.",
            )
        ]


class FakeRadon:
    def analyze_project(self, _root):
        issue = Issue(
            severity="medium",
            type="CyclomaticComplexity",
            file="pkg/a.py",
            line=2,
            message="Function has high cyclomatic complexity.",
            suggestion="Consider splitting complex branches into smaller functions.",
        )
        return [issue, issue]


class FakeDependencyAnalyzer:
    def __init__(self, _root):
        pass

    def build_graph(self):
        return object()

    def detect_cycles(self, _graph):
        return [
            Issue(
                severity="high",
                type="CircularDependency",
                file="pkg/a.py",
                line=1,
                message="Circular dependency detected: pkg.a -> pkg.b -> pkg.a",
                suggestion="Break the cycle by extracting shared abstractions or moving dependencies to a lower-level module.",
            )
        ]

    def detect_high_coupling(self, _graph):
        return []


class FakeGodDetector:
    def __init__(self, _root):
        pass

    def analyze_project(self, **_kwargs):
        return [
            Issue(
                severity="medium",
                type="GodClass",
                file="pkg/a.py",
                line=3,
                message="Class appears to have too many responsibilities.",
                suggestion="Split this class into smaller classes with focused responsibilities.",
            )
        ]


def test_project_reviewer_aggregates_dedupes_and_sorts(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")

    issues = ProjectReviewer(
        ruff_adapter=FakeRuff(),
        radon_adapter=FakeRadon(),
        dependency_analyzer_cls=FakeDependencyAnalyzer,
        god_detector_cls=FakeGodDetector,
    ).review(tmp_path)

    assert [issue.type for issue in issues][:2] == ["CircularDependency", "CyclomaticComplexity"]
    assert sum(issue.type == "CyclomaticComplexity" for issue in issues) == 1
    assert {issue.type for issue in issues} >= {"MagicNumberRule", "RuffUnusedImport", "GodClass"}


def test_project_reviewer_json_is_valid(tmp_path: Path) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "a.py").write_text("def run(a):\n    return a + 42\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "issues" in payload
