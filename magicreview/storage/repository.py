"""Repository and persistence services for Dashboard data."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.report.cli_formatters import normalize_result
from magicreview.dashboard.classifier import classify_issue
from magicreview.storage.database import connect, init_db


class ReviewRepository:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = db_path
        init_db(db_path)

    def upsert_project(self, *, name: str, repository_url: str | None = None, provider: str = "local", default_branch: str | None = None) -> int:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO projects(name, repository_url, provider, default_branch)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET
                    repository_url=COALESCE(excluded.repository_url, projects.repository_url),
                    provider=excluded.provider,
                    default_branch=COALESCE(excluded.default_branch, projects.default_branch),
                    updated_at=CURRENT_TIMESTAMP
                """,
                (name, repository_url, provider, default_branch),
            )
            row = connection.execute("SELECT id FROM projects WHERE name = ?", (name,)).fetchone()
            return int(row["id"])

    def insert_review_run(self, data: dict[str, Any]) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO review_runs(
                    project_id, source, target_type, target_ref, commit_sha, pull_request_number, status,
                    total_issues, critical_count, high_count, medium_count, low_count,
                    duration_ms, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("project_id"),
                    data["source"],
                    data["target_type"],
                    data["target_ref"],
                    data.get("commit_sha"),
                    data.get("pull_request_number"),
                    data.get("status", "completed"),
                    data["summary"]["total"],
                    data["summary"]["critical"],
                    data["summary"]["high"],
                    data["summary"]["medium"],
                    data["summary"]["low"],
                    data.get("duration_ms", 0),
                    json.dumps(data.get("metadata", {}), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def insert_issue(self, review_run_id: int, issue: dict[str, Any], fingerprint: str) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO issue_records(
                    review_run_id, severity, type, file, line, message, suggestion, category, agent_name, fingerprint
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    review_run_id,
                    issue["severity"],
                    issue["type"],
                    issue["file"],
                    int(issue["line"]),
                    issue["message"],
                    issue["suggestion"],
                    classify_issue(issue["type"]),
                    issue.get("agent_name"),
                    fingerprint,
                ),
            )

    def upsert_github_pr(self, *, project_id: int | None, owner: str, repo: str, pull_number: int, head_sha: str | None, base_sha: str | None, author: str | None, state: str | None, last_review_run_id: int) -> None:
        with connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO github_pull_requests(project_id, owner, repo, pull_number, head_sha, base_sha, author, state, last_review_run_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(owner, repo, pull_number) DO UPDATE SET
                    project_id=excluded.project_id,
                    head_sha=excluded.head_sha,
                    base_sha=excluded.base_sha,
                    author=excluded.author,
                    state=excluded.state,
                    last_review_run_id=excluded.last_review_run_id,
                    updated_at=CURRENT_TIMESTAMP
                """,
                (project_id, owner, repo, pull_number, head_sha, base_sha, author, state, last_review_run_id),
            )

    def list_projects(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT p.*,
                       MAX(r.finished_at) AS last_review_at,
                       COALESCE(SUM(r.total_issues), 0) AS issue_count,
                       COALESCE(SUM(r.high_count), 0) AS high_count
                FROM projects p
                LEFT JOIN review_runs r ON r.project_id = p.id
                GROUP BY p.id
                ORDER BY p.updated_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
            return [_row(row) for row in rows]

    def get_project(self, project_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return _row(row) if row else None

    def list_reviews(self, *, project_id: int | None = None, severity: str | None = None, source: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_id is not None:
            clauses.append("project_id = ?")
            params.append(project_id)
        if source:
            clauses.append("source = ?")
            params.append(source)
        if severity:
            clauses.append(f"{severity}_count > 0")
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        params.extend([limit, offset])
        with connect(self.db_path) as connection:
            rows = connection.execute(f"SELECT * FROM review_runs {where} ORDER BY finished_at DESC, id DESC LIMIT ? OFFSET ?", params).fetchall()
            return [_with_metadata(row) for row in rows]

    def get_review_run(self, review_run_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM review_runs WHERE id = ?", (review_run_id,)).fetchone()
            return _with_metadata(row) if row else None

    def get_review_issues(self, review_run_id: int, *, severity: str | None = None, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
        clauses = ["review_run_id = ?"]
        params: list[Any] = [review_run_id]
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        params.extend([limit, offset])
        with connect(self.db_path) as connection:
            rows = connection.execute(
                f"SELECT * FROM issue_records WHERE {' AND '.join(clauses)} ORDER BY id ASC LIMIT ? OFFSET ?",
                params,
            ).fetchall()
            return [_row(row) for row in rows]

    def insert_network_audit(self, data: dict[str, Any]) -> int:
        with connect(self.db_path) as connection:
            cursor = connection.execute(
                """
                INSERT INTO network_audit_records(
                    source, provider, operation, code_sharing_mode, project_name, target_ref, status, error_type, metadata_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["source"],
                    data["provider"],
                    data["operation"],
                    data["code_sharing_mode"],
                    data.get("project_name"),
                    data.get("target_ref"),
                    data["status"],
                    data.get("error_type"),
                    json.dumps(data.get("metadata", {}), ensure_ascii=False),
                ),
            )
            return int(cursor.lastrowid)

    def list_network_audit(self, *, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        with connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT * FROM network_audit_records ORDER BY timestamp DESC, id DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            return [_with_metadata(row) for row in rows]

    def get_network_audit(self, audit_id: int) -> dict[str, Any] | None:
        with connect(self.db_path) as connection:
            row = connection.execute("SELECT * FROM network_audit_records WHERE id = ?", (audit_id,)).fetchone()
            return _with_metadata(row) if row else None


class ReviewPersistenceService:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.repository = ReviewRepository(db_path)

    def save_review_result(
        self,
        result: dict[str, Any],
        *,
        source: str,
        target_type: str,
        target_ref: str,
        project_name: str | None = None,
        repository_url: str | None = None,
        commit_sha: str | None = None,
        pull_request_number: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        started = time.perf_counter()
        normalized = normalize_result(result)
        project_id = None
        if project_name:
            project_id = self.repository.upsert_project(name=project_name, repository_url=repository_url, provider=source)
        review_run_id = self.repository.insert_review_run(
            {
                "project_id": project_id,
                "source": source,
                "target_type": target_type,
                "target_ref": target_ref,
                "commit_sha": commit_sha,
                "pull_request_number": pull_request_number,
                "status": "completed",
                "summary": normalized["summary"],
                "duration_ms": int((time.perf_counter() - started) * 1000),
                "metadata": metadata or {},
            }
        )
        for issue in normalized["issues"]:
            self.repository.insert_issue(review_run_id, issue, self.fingerprint(issue))
        metadata = metadata or {}
        if source == "github" and project_name and pull_request_number is not None:
            owner, _, repo = project_name.partition("/")
            self.repository.upsert_github_pr(
                project_id=project_id,
                owner=owner,
                repo=repo,
                pull_number=pull_request_number,
                head_sha=commit_sha,
                base_sha=metadata.get("base_sha"),
                author=metadata.get("author") or metadata.get("sender"),
                state=metadata.get("state"),
                last_review_run_id=review_run_id,
            )
        return review_run_id

    def get_review_run(self, review_run_id: int) -> dict[str, Any] | None:
        return self.repository.get_review_run(review_run_id)

    def list_review_runs(self, **kwargs: Any) -> list[dict[str, Any]]:
        return self.repository.list_reviews(**kwargs)

    def get_project_summary(self, project_id: int) -> dict[str, Any]:
        project = self.repository.get_project(project_id)
        reviews = self.repository.list_reviews(project_id=project_id, limit=1000)
        return {"project": project, "review_count": len(reviews), "total_issues": sum(review["total_issues"] for review in reviews)}

    def save_network_audit(
        self,
        *,
        source: str,
        provider: str,
        operation: str,
        code_sharing_mode: str,
        status: str,
        project_name: str | None = None,
        target_ref: str | None = None,
        error_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        sanitized = self._sanitize_metadata(metadata or {})
        return self.repository.insert_network_audit(
            {
                "source": source,
                "provider": provider,
                "operation": operation,
                "code_sharing_mode": code_sharing_mode,
                "project_name": project_name,
                "target_ref": target_ref,
                "status": status,
                "error_type": error_type,
                "metadata": sanitized,
            }
        )

    @staticmethod
    def fingerprint(issue: dict[str, Any]) -> str:
        payload = "|".join(str(issue.get(key, "")) for key in ("type", "file", "line", "message"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
        blocked = {"api_key", "token", "private_key", "prompt", "authorization", "secret"}
        return {key: value for key, value in metadata.items() if key.lower() not in blocked}


def _row(row: Any) -> dict[str, Any]:
    return dict(row)


def _with_metadata(row: Any) -> dict[str, Any]:
    data = dict(row)
    try:
        data["metadata"] = json.loads(data.pop("metadata_json", "{}"))
    except json.JSONDecodeError:
        data["metadata"] = {}
    return data
