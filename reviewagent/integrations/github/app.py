"""FastAPI entry point for the ReviewAgent GitHub App."""

from __future__ import annotations

from typing import Any, Callable

from reviewagent.integrations.github.config import GitHubAppConfig
from reviewagent.integrations.github.webhook import GitHubWebhookHandler


try:
    from fastapi import FastAPI, Header, Request, Response, status
except ModuleNotFoundError:  # pragma: no cover
    class FastAPI:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.routes: dict[str, Callable[..., Any]] = {}

        def get(self, path: str):
            def decorator(func):
                self.routes[f"GET {path}"] = func
                return func

            return decorator

        def post(self, path: str):
            def decorator(func):
                self.routes[f"POST {path}"] = func
                return func

            return decorator

    class Response:  # type: ignore[no-redef]
        def __init__(self, status_code: int = 200) -> None:
            self.status_code = status_code

    class status:  # type: ignore[no-redef]
        HTTP_401_UNAUTHORIZED = 401

    def Header(*_args: Any, default: Any = None, **_kwargs: Any) -> Any:  # type: ignore[no-redef]
        return default

    Request = Any  # type: ignore[assignment]


app = FastAPI(title="ReviewAgent GitHub App")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "github-app"}


@app.post("/webhook")
async def webhook(
    request: Request,
    response: Response,
    x_hub_signature_256: str | None = Header(default=None, alias="X-Hub-Signature-256"),
    x_github_event: str | None = Header(default=None, alias="X-GitHub-Event"),
) -> dict[str, Any]:
    payload = await request.body()
    status_code, body = GitHubWebhookHandler(config=GitHubAppConfig.from_env()).handle(
        payload_bytes=payload,
        signature=x_hub_signature_256,
        event_name=x_github_event,
    )
    response.status_code = status_code
    return body


def main() -> None:
    config = GitHubAppConfig.from_env()
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("uvicorn is required to run the GitHub App server. Install project dependencies first.") from exc
    uvicorn.run("reviewagent.integrations.github.app:app", host=config.host, port=config.port)


if __name__ == "__main__":
    main()
