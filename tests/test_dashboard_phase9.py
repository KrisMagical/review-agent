import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from magicreview.dashboard import app as dashboard_app_module
from magicreview.dashboard.classifier import classify_issue
from magicreview.dashboard.service import StatisticsService
from magicreview.integrations.github.client import GitHubAppClient
from magicreview.integrations.github.config import GitHubAppConfig
from magicreview.integrations.github.models import PullRequestEvent
from magicreview.integrations.github.reviewer import GitHubPullRequestReviewer
from magicreview.storage.database import init_db
from magicreview.storage.repository import ReviewPersistenceService, ReviewRepository


def result_payload() -> dict:
    return {
        "issues": [
            {"severity": "high", "type": "SQLInjectionRule", "file": "app/db.py", "line": 2, "message": "SQL", "suggestion": "Use params."},
            {"severity": "medium", "type": "FunctionTooLongRule", "file": "app/service.py", "line": 10, "message": "Long", "suggestion": "Split it."},
            {"severity": "low", "type": "CircularDependency", "file": "app/a.py", "line": 1, "message": "Cycle", "suggestion": "Break it."},
        ]
    }


def test_storage_init_save_summary_fingerprint_and_empty_issues(tmp_path: Path) -> None:
    db_path = tmp_path / "magicreview.db"
    init_db(db_path)
    service = ReviewPersistenceService(db_path)

    review_id = service.save_review_result(
        result_payload(),
        source="cli",
        target_type="project",
        target_ref=".",
        project_name="demo",
        metadata={"author": "alice"},
    )
    empty_id = service.save_review_result({"issues": []}, source="cli", target_type="diff", target_ref="<stdin>")

    review = service.get_review_run(review_id)
    empty = service.get_review_run(empty_id)
    issues = service.repository.get_review_issues(review_id)

    assert review is not None
    assert review["total_issues"] == 3
    assert review["high_count"] == 1
    assert empty is not None
    assert empty["total_issues"] == 0
    assert len(issues) == 3
    assert issues[0]["fingerprint"] == service.fingerprint(result_payload()["issues"][0])


def test_repository_lists_projects_reviews_issues_with_filters_and_pagination(tmp_path: Path) -> None:
    service = ReviewPersistenceService(tmp_path / "db.sqlite")
    review_id = service.save_review_result(result_payload(), source="cli", target_type="project", target_ref=".", project_name="demo")
    service.save_review_result({"issues": []}, source="cli", target_type="file", target_ref="a.py", project_name="demo")

    repo = service.repository
    assert repo.list_projects(limit=1, offset=0)[0]["name"] == "demo"
    assert repo.list_reviews(project_id=1, limit=1, offset=0)
    assert repo.list_reviews(severity="high")
    assert repo.get_review_run(review_id)["id"] == review_id
    assert len(repo.get_review_issues(review_id, severity="high")) == 1


def test_statistics_service_overview_trends_and_team_stats(tmp_path: Path) -> None:
    service = ReviewPersistenceService(tmp_path / "stats.db")
    service.save_review_result(
        result_payload(),
        source="github",
        target_type="pull_request",
        target_ref="octo/repo#7",
        project_name="octo/repo",
        commit_sha="sha",
        pull_request_number=7,
        metadata={"author": "alice", "sender": "alice", "base_sha": "base", "state": "open"},
    )
    stats = StatisticsService(tmp_path / "stats.db")

    assert stats.overview()["issue_count"] == 3
    assert stats.issue_trend()
    assert stats.bug_trend()
    assert stats.technical_debt_trend()
    assert stats.architecture_risk_trend()
    team = stats.team_stats()
    assert team["reviews_by_author"]["alice"] == 1
    assert team["top_risky_files"]


def test_dashboard_api_functions_and_not_found(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "api.db"
    monkeypatch.setenv("MGREVIEW_DB_PATH", str(db_path))
    service = ReviewPersistenceService(db_path)
    review_id = service.save_review_result(result_payload(), source="cli", target_type="project", target_ref=".", project_name="demo")

    assert dashboard_app_module.health() == {"status": "ok", "service": "dashboard"}
    assert dashboard_app_module.api_projects()
    assert dashboard_app_module.api_reviews()
    assert dashboard_app_module.api_review(review_id)["id"] == review_id
    assert dashboard_app_module.api_review_issues(review_id)
    assert dashboard_app_module.api_stats_overview()["issue_count"] == 3
    assert dashboard_app_module.api_issue_trend()

    with pytest.raises(Exception):
        dashboard_app_module.api_review(9999)


def test_dashboard_pages_return_html_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "pages.db"
    monkeypatch.setenv("MGREVIEW_DB_PATH", str(db_path))
    service = ReviewPersistenceService(db_path)
    review_id = service.save_review_result(result_payload(), source="cli", target_type="project", target_ref=".", project_name="demo<script>")

    assert "MagicReview" in str(dashboard_app_module.dashboard_index(None))
    assert "Projects" in str(dashboard_app_module.dashboard_projects(None))
    assert "demo" in str(dashboard_app_module.dashboard_project_detail(None, 1))
    assert f"Review #{review_id}" in str(dashboard_app_module.dashboard_review_detail(None, review_id))


def test_cli_save_and_dashboard_init_db(tmp_path: Path) -> None:
    db_path = tmp_path / "cli.db"
    target = tmp_path / "bad.py"
    target.write_text("def run(a):\n    return a + 42\n", encoding="utf-8")
    env = {**os.environ, "MGREVIEW_DB_PATH": str(db_path)}

    review_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "file", str(target), "--save", "--format", "json"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    init_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "dashboard", "init-db"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    assert "issues" in json.loads(review_result.stdout)
    assert json.loads(init_result.stdout)["status"] == "ok"
    assert ReviewRepository(db_path).list_reviews()


class FakeGitHubClient(GitHubAppClient):
    def __init__(self) -> None:
        pass

    def get_installation_token(self, installation_id: int) -> str:
        return "token"

    def get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> str:
        return "diff --git a/app/db.py b/app/db.py\n--- a/app/db.py\n+++ b/app/db.py\n@@ -0,0 +1,1 @@\n+print('x')\n"


class FakeCommenter:
    def publish(self, event, result, diff_text, *, summary=True, inline=True, errors=None):
        return type("R", (), {"status": "completed", "issues_count": len(result["issues"]), "summary_comment_id": 1, "inline_comments_created": 0, "inline_comments_skipped": 0, "errors": list(errors or [])})()


class FakeReviewService:
    def review_diff(self, diff: str) -> dict:
        return result_payload()


def test_github_app_save_results_and_persistence_failure_is_nonfatal(tmp_path: Path) -> None:
    persistence = ReviewPersistenceService(tmp_path / "github.db")
    reviewer = GitHubPullRequestReviewer(
        client=FakeGitHubClient(),
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s", save_results=True),
        review_service=FakeReviewService(),  # type: ignore[arg-type]
        commenter=FakeCommenter(),  # type: ignore[arg-type]
        persistence_service=persistence,
    )
    event = PullRequestEvent(installation_id=1, owner="octo", repo="repo", pull_number=7, head_sha="sha", base_sha="base", metadata={"author": "alice"})

    result = reviewer.review_pull_request(event)

    assert result.status == "completed"
    assert persistence.repository.list_reviews(source="github")
    metadata = persistence.repository.list_reviews(source="github")[0]["metadata"]
    assert "token" not in metadata
    assert "private" not in json.dumps(metadata).lower()

    class FailingPersistence:
        def save_review_result(self, *args, **kwargs):
            raise RuntimeError("db down")

    failing = GitHubPullRequestReviewer(
        client=FakeGitHubClient(),
        config=GitHubAppConfig(app_id="1", private_key="test", webhook_secret="s", save_results=True),
        review_service=FakeReviewService(),  # type: ignore[arg-type]
        commenter=FakeCommenter(),  # type: ignore[arg-type]
        persistence_service=FailingPersistence(),  # type: ignore[arg-type]
    )
    failed_save = failing.review_pull_request(event)
    assert failed_save.status == "completed"
    assert failed_save.errors


def test_issue_classifier_categories() -> None:
    assert classify_issue("SQLInjectionRule") == "security"
    assert classify_issue("KeyErrorRule") == "bug"
    assert classify_issue("GodClass") == "architecture"
    assert classify_issue("EnterpriseNoSelectStar") == "enterprise"
