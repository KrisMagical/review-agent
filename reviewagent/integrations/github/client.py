"""Small GitHub App API client with mock-friendly HTTP boundaries."""

from __future__ import annotations

import base64
import json
import time
from typing import Any

import httpx


class GitHubClientError(RuntimeError):
    """Raised when a GitHub API operation fails."""


class GitHubAppClient:
    api_url = "https://api.github.com"

    def __init__(
        self,
        *,
        app_id: str,
        private_key: str,
        token: str | None = None,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.app_id = app_id
        self.private_key = private_key
        self.token = token
        self.http = http_client or httpx.Client(timeout=20)

    def create_jwt(self) -> str:
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": self.app_id}
        if self.private_key.startswith("test"):
            return self._test_jwt(payload)
        try:
            import jwt

            return str(jwt.encode(payload, self.private_key, algorithm="RS256"))
        except ImportError as exc:
            raise GitHubClientError("PyJWT is required for GitHub App authentication.") from exc
        except Exception as exc:
            raise GitHubClientError("Failed to create GitHub App JWT from the configured private key.") from exc

    def get_installation_token(self, installation_id: int) -> str:
        response = self.http.post(
            f"{self.api_url}/app/installations/{installation_id}/access_tokens",
            headers=self._headers(token=self.create_jwt(), accept="application/vnd.github+json"),
        )
        self._raise_for_status(response)
        token = response.json().get("token")
        if not token:
            raise GitHubClientError("GitHub installation token response did not include a token.")
        self.token = str(token)
        return self.token

    def get_pull_request_diff(self, owner: str, repo: str, pull_number: int) -> str:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}",
            headers=self._headers(accept="application/vnd.github.v3.diff"),
        )
        self._raise_for_status(response)
        return response.text

    def get_pull_request(self, owner: str, repo: str, pull_number: int) -> dict[str, Any]:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return dict(response.json())

    def get_tree(self, owner: str, repo: str, sha: str, *, recursive: bool = True) -> dict[str, Any]:
        suffix = "?recursive=1" if recursive else ""
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/git/trees/{sha}{suffix}",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        payload = dict(response.json())
        if payload.get("truncated"):
            raise GitHubClientError("GitHub tree response was truncated.")
        return payload

    def get_blob_text(self, owner: str, repo: str, blob_sha: str) -> str:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/git/blobs/{blob_sha}",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        payload = response.json()
        content = str(payload.get("content", ""))
        encoding = str(payload.get("encoding", ""))
        if encoding == "base64":
            return base64.b64decode(content).decode("utf-8")
        return content

    def get_repository_file_tree_for_ref(self, owner: str, repo: str, ref: str) -> dict[str, Any]:
        return self.get_tree(owner, repo, ref, recursive=True)

    def list_pull_request_files(self, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}/files",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return list(response.json())

    def get_url_text(self, url: str) -> str:
        response = self.http.get(url, headers=self._headers(accept="text/plain"))
        self._raise_for_status(response)
        return response.text

    def list_issue_comments(self, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/issues/{pull_number}/comments",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return list(response.json())

    def create_issue_comment(self, owner: str, repo: str, pull_number: int, body: str) -> dict[str, Any]:
        response = self.http.post(
            f"{self.api_url}/repos/{owner}/{repo}/issues/{pull_number}/comments",
            headers=self._headers(),
            json={"body": body},
        )
        self._raise_for_status(response)
        return dict(response.json())

    def update_issue_comment(self, owner: str, repo: str, comment_id: int, body: str) -> dict[str, Any]:
        response = self.http.patch(
            f"{self.api_url}/repos/{owner}/{repo}/issues/comments/{comment_id}",
            headers=self._headers(),
            json={"body": body},
        )
        self._raise_for_status(response)
        return dict(response.json())

    def list_review_comments(self, owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
        response = self.http.get(
            f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}/comments",
            headers=self._headers(),
        )
        self._raise_for_status(response)
        return list(response.json())

    def create_review_comment(
        self,
        owner: str,
        repo: str,
        pull_number: int,
        *,
        body: str,
        commit_id: str,
        path: str,
        line: int,
        side: str = "RIGHT",
    ) -> dict[str, Any]:
        response = self.http.post(
            f"{self.api_url}/repos/{owner}/{repo}/pulls/{pull_number}/comments",
            headers=self._headers(),
            json={"body": body, "commit_id": commit_id, "path": path, "line": line, "side": side},
        )
        self._raise_for_status(response)
        return dict(response.json())

    def create_check_run(
        self,
        owner: str,
        repo: str,
        *,
        name: str,
        head_sha: str,
        conclusion: str,
        summary: str,
    ) -> dict[str, Any]:
        response = self.http.post(
            f"{self.api_url}/repos/{owner}/{repo}/check-runs",
            headers=self._headers(accept="application/vnd.github+json"),
            json={
                "name": name,
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "output": {"title": name, "summary": summary},
            },
        )
        self._raise_for_status(response)
        return dict(response.json())

    def _headers(self, *, token: str | None = None, accept: str = "application/vnd.github+json") -> dict[str, str]:
        active_token = token or self.token
        headers = {"Accept": accept, "X-GitHub-Api-Version": "2022-11-28"}
        if active_token:
            headers["Authorization"] = f"Bearer {active_token}"
        return headers

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.status_code >= 400:
            raise GitHubClientError(f"GitHub API request failed with status {response.status_code}.")

    @staticmethod
    def _test_jwt(payload: dict[str, Any]) -> str:
        def b64(data: bytes) -> str:
            return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

        header = {"alg": "RS256", "typ": "JWT"}
        return f"{b64(json.dumps(header).encode())}.{b64(json.dumps(payload).encode())}.test-signature"
