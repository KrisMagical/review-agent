"""Dashboard statistics services."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from magicreview.dashboard.classifier import is_architecture_risk_type, is_bug_type, is_technical_debt_type
from magicreview.storage.database import connect, init_db
from magicreview.storage.repository import ReviewRepository


class StatisticsService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        init_db(db_path)
        self.repository = ReviewRepository(db_path)

    def overview(self) -> dict[str, int]:
        with connect(self.db_path) as connection:
            project_count = int(connection.execute("SELECT COUNT(*) AS value FROM projects").fetchone()["value"])
            review_run_count = int(connection.execute("SELECT COUNT(*) AS value FROM review_runs").fetchone()["value"])
            row = connection.execute(
                """
                SELECT COALESCE(SUM(total_issues), 0) AS total,
                       COALESCE(SUM(critical_count), 0) AS critical,
                       COALESCE(SUM(high_count), 0) AS high,
                       COALESCE(SUM(medium_count), 0) AS medium,
                       COALESCE(SUM(low_count), 0) AS low
                FROM review_runs
                """
            ).fetchone()
        return {
            "project_count": project_count,
            "review_run_count": review_run_count,
            "issue_count": int(row["total"]),
            "critical_count": int(row["critical"]),
            "high_count": int(row["high"]),
            "medium_count": int(row["medium"]),
            "low_count": int(row["low"]),
        }

    def issue_trend(self) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT substr(finished_at, 1, 10) AS day,
                       SUM(total_issues) AS total,
                       SUM(critical_count) AS critical,
                       SUM(high_count) AS high,
                       SUM(medium_count) AS medium,
                       SUM(low_count) AS low
                FROM review_runs
                GROUP BY day
                ORDER BY day
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def category_trend(self, predicate) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT substr(i.created_at, 1, 10) AS day, i.type, COUNT(*) AS count
                FROM issue_records i
                GROUP BY day, i.type
                ORDER BY day
                """
            ).fetchall()
        grouped: dict[str, int] = {}
        for row in rows:
            if predicate(str(row["type"])):
                grouped[str(row["day"])] = grouped.get(str(row["day"]), 0) + int(row["count"])
        return [{"day": day, "count": count} for day, count in sorted(grouped.items())]

    def bug_trend(self) -> list[dict[str, Any]]:
        return self.category_trend(is_bug_type)

    def technical_debt_trend(self) -> list[dict[str, Any]]:
        return self.category_trend(is_technical_debt_type)

    def architecture_risk_trend(self) -> list[dict[str, Any]]:
        return self.category_trend(is_architecture_risk_type)

    def team_stats(self) -> dict[str, Any]:
        reviews = self.repository.list_reviews(limit=10000)
        reviews_by_author: dict[str, int] = {}
        issues_by_author: dict[str, int] = {}
        high_risk_prs: list[dict[str, Any]] = []
        top_files: dict[str, int] = {}
        for review in reviews:
            metadata = review.get("metadata", {})
            author = metadata.get("author") or metadata.get("sender") or "unknown"
            reviews_by_author[author] = reviews_by_author.get(author, 0) + 1
            issues_by_author[author] = issues_by_author.get(author, 0) + int(review.get("total_issues", 0))
            if int(review.get("high_count", 0)) > 0 or int(review.get("critical_count", 0)) > 0:
                high_risk_prs.append(review)
            for issue in self.repository.get_review_issues(int(review["id"]), limit=1000):
                top_files[str(issue["file"])] = top_files.get(str(issue["file"]), 0) + 1
        return {
            "reviews_by_author": reviews_by_author,
            "issues_by_author": issues_by_author,
            "high_risk_prs": high_risk_prs[:20],
            "top_risky_files": sorted(
                [{"file": file, "count": count} for file, count in top_files.items()],
                key=lambda item: item["count"],
                reverse=True,
            )[:20],
        }
