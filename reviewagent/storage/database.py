"""SQLite database initialization for ReviewAgent."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def default_db_path() -> Path:
    configured = os.getenv("REVIEWAGENT_DB_PATH")
    if configured:
        return Path(configured).expanduser()
    return Path(".reviewagent") / "reviewagent.db"


def connect(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: str | Path | None = None) -> None:
    with connect(db_path) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                repository_url TEXT,
                provider TEXT DEFAULT 'local',
                default_branch TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS review_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                source TEXT NOT NULL,
                target_type TEXT NOT NULL,
                target_ref TEXT NOT NULL,
                commit_sha TEXT,
                pull_request_number INTEGER,
                status TEXT NOT NULL,
                total_issues INTEGER NOT NULL DEFAULT 0,
                critical_count INTEGER NOT NULL DEFAULT 0,
                high_count INTEGER NOT NULL DEFAULT 0,
                medium_count INTEGER NOT NULL DEFAULT 0,
                low_count INTEGER NOT NULL DEFAULT 0,
                started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                finished_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS issue_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                review_run_id INTEGER NOT NULL,
                severity TEXT NOT NULL,
                type TEXT NOT NULL,
                file TEXT NOT NULL,
                line INTEGER NOT NULL,
                message TEXT NOT NULL,
                suggestion TEXT NOT NULL,
                category TEXT,
                agent_name TEXT,
                fingerprint TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(review_run_id) REFERENCES review_runs(id)
            );

            CREATE TABLE IF NOT EXISTS github_pull_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER,
                owner TEXT NOT NULL,
                repo TEXT NOT NULL,
                pull_number INTEGER NOT NULL,
                head_sha TEXT,
                base_sha TEXT,
                title TEXT,
                author TEXT,
                state TEXT,
                last_review_run_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(owner, repo, pull_number),
                FOREIGN KEY(project_id) REFERENCES projects(id),
                FOREIGN KEY(last_review_run_id) REFERENCES review_runs(id)
            );

            CREATE TABLE IF NOT EXISTS network_audit_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                source TEXT NOT NULL,
                provider TEXT NOT NULL,
                operation TEXT NOT NULL,
                code_sharing_mode TEXT NOT NULL,
                project_name TEXT,
                target_ref TEXT,
                status TEXT NOT NULL,
                error_type TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS model_provider_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL DEFAULT 'default',
                provider TEXT NOT NULL DEFAULT 'none',
                enabled INTEGER NOT NULL DEFAULT 0,
                model TEXT,
                base_url TEXT,
                api_key_value TEXT,
                api_key_source TEXT NOT NULL DEFAULT 'none',
                timeout_seconds INTEGER NOT NULL DEFAULT 30,
                max_context_chars INTEGER NOT NULL DEFAULT 60000,
                code_sharing_mode TEXT NOT NULL DEFAULT 'none',
                allow_network INTEGER NOT NULL DEFAULT 0,
                allow_llm INTEGER NOT NULL DEFAULT 0,
                audit_enabled INTEGER NOT NULL DEFAULT 1,
                organization TEXT,
                azure_endpoint TEXT,
                azure_deployment TEXT,
                azure_api_version TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
