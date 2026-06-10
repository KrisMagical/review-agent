"""FastAPI Dashboard for ReviewAgent governance data."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs

from reviewagent.dashboard.auth import (
    AUTH_SESSION_KEY,
    AUTH_USER_KEY,
    is_valid_api_key,
    is_valid_login,
    load_auth_config,
    login_url_for,
    parse_basic_auth,
    parse_bearer_token,
    session_secret,
)
from reviewagent.dashboard.hosted_review import HostedReviewService, max_upload_bytes
from reviewagent.dashboard.model_settings import ModelProviderTester, ModelSettingsRepository
from reviewagent.dashboard.service import StatisticsService
from reviewagent.storage.database import init_db
from reviewagent.storage.repository import ReviewRepository

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.templating import Jinja2Templates
except ModuleNotFoundError:  # pragma: no cover
    class FastAPI:  # type: ignore[no-redef]
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.routes = {}

        def get(self, path: str, **_kwargs: Any):
            def decorator(func):
                self.routes[f"GET {path}"] = func
                return func

            return decorator

    class HTTPException(Exception):  # type: ignore[no-redef]
        def __init__(self, status_code: int, detail: str) -> None:
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    class HTMLResponse(str):  # type: ignore[no-redef]
        pass

    class JSONResponse(dict):  # type: ignore[no-redef]
        pass

    class RedirectResponse(str):  # type: ignore[no-redef]
        pass

    Request = Any  # type: ignore[assignment]
    Jinja2Templates = None  # type: ignore[assignment]
    StaticFiles = None  # type: ignore[assignment]

try:
    from starlette.middleware.sessions import SessionMiddleware
except ModuleNotFoundError:  # pragma: no cover
    SessionMiddleware = None  # type: ignore[assignment]


BASE_DIR = Path(__file__).parent
app = FastAPI(title="ReviewAgent Dashboard")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates")) if Jinja2Templates else None
if StaticFiles is not None:
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


PUBLIC_PATHS = {"/health", "/login", "/logout"}
PROTECTED_PAGE_PREFIXES = ("/dashboard", "/projects", "/reviews", "/audit", "/settings", "/review")
PROTECTED_API_PREFIXES = ("/api/",)


def repository() -> ReviewRepository:
    return ReviewRepository()


def stats_service() -> StatisticsService:
    return StatisticsService()


def model_settings_repository() -> ModelSettingsRepository:
    return ModelSettingsRepository()


def hosted_review_service() -> HostedReviewService:
    return HostedReviewService()


def template_response(name: str, request: Request, context: dict[str, Any], status_code: int = 200) -> Any:
    if templates is None:
        return HTMLResponse("")
    try:
        return templates.TemplateResponse(request, name, context, status_code=status_code)
    except TypeError:
        return templates.TemplateResponse(name, {"request": request, **context}, status_code=status_code)


def _path_requires_auth(path: str) -> bool:
    if path == "/":
        return True
    if path in PUBLIC_PATHS or path.startswith("/static/"):
        return False
    return path.startswith(PROTECTED_PAGE_PREFIXES) or path.startswith(PROTECTED_API_PREFIXES)


def _is_api_path(path: str) -> bool:
    return path.startswith(PROTECTED_API_PREFIXES)


def _request_is_authenticated(request: Request) -> bool:
    cfg = load_auth_config()
    if not cfg.enabled:
        return True

    try:
        if request.session.get(AUTH_SESSION_KEY) is True:
            return True
    except AssertionError:
        pass

    authorization = request.headers.get("authorization")
    bearer = parse_bearer_token(authorization)
    if bearer and is_valid_api_key(bearer, cfg):
        return True

    if cfg.basic_auth_enabled:
        credentials = parse_basic_auth(authorization)
        if credentials and is_valid_login(credentials[0], credentials[1], cfg):
            return True

    return False


@app.middleware("http")
async def dashboard_auth_middleware(request: Request, call_next: Any) -> Any:
    cfg = load_auth_config()
    path = request.url.path
    if not cfg.enabled or not _path_requires_auth(path) or _request_is_authenticated(request):
        return await call_next(request)

    if _is_api_path(path):
        return JSONResponse({"detail": "Authentication required"}, status_code=401)
    return RedirectResponse(login_url_for(path), status_code=303)


if SessionMiddleware is not None:
    app.add_middleware(
        SessionMiddleware,
        secret_key=session_secret(),
        https_only=load_auth_config().cookie_secure,
        same_site="lax",
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "dashboard"}


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/dashboard") -> Any:
    if templates is None:
        return HTMLResponse("<h1>Login</h1>")
    return template_response("login.html", request, {"error": "", "next": next})


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request) -> Any:
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]
    next_url = form.get("next", ["/dashboard"])[0] or "/dashboard"
    if not next_url.startswith("/"):
        next_url = "/dashboard"

    if is_valid_login(username, password):
        request.session[AUTH_SESSION_KEY] = True
        request.session[AUTH_USER_KEY] = username
        return RedirectResponse(next_url, status_code=303)

    if templates is None:
        return HTMLResponse("Invalid username or password.", status_code=401)
    return template_response(
        "login.html",
        request,
        {"error": "Invalid username or password.", "next": next_url},
        status_code=401,
    )


@app.get("/logout")
def logout(request: Request) -> Any:
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


def dashboard_host_port() -> tuple[str, int]:
    return (
        os.getenv("REVIEWAGENT_DASHBOARD_HOST", "127.0.0.1"),
        int(os.getenv("REVIEWAGENT_DASHBOARD_PORT", "8080")),
    )


@app.get("/api/projects")
def api_projects(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_projects(limit=limit, offset=offset)


@app.get("/api/projects/{project_id}")
def api_project(project_id: int) -> dict[str, Any]:
    project = repository().get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    return project


@app.get("/api/projects/{project_id}/reviews")
def api_project_reviews(project_id: int, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_reviews(project_id=project_id, limit=limit, offset=offset)


@app.get("/api/reviews")
def api_reviews(project_id: int | None = None, severity: str | None = None, source: str | None = None, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_reviews(project_id=project_id, severity=severity, source=source, limit=limit, offset=offset)


@app.get("/api/reviews/{review_run_id}")
def api_review(review_run_id: int) -> dict[str, Any]:
    review = repository().get_review_run(review_run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review run not found.")
    return review


@app.get("/api/reviews/{review_run_id}/issues")
def api_review_issues(review_run_id: int, severity: str | None = None, limit: int = 500, offset: int = 0) -> list[dict[str, Any]]:
    return repository().get_review_issues(review_run_id, severity=severity, limit=limit, offset=offset)


@app.get("/api/stats/overview")
def api_stats_overview() -> dict[str, int]:
    return stats_service().overview()


@app.get("/api/stats/trends/issues")
def api_issue_trend() -> list[dict[str, Any]]:
    return stats_service().issue_trend()


@app.get("/api/stats/trends/bugs")
def api_bug_trend() -> list[dict[str, Any]]:
    return stats_service().bug_trend()


@app.get("/api/stats/trends/technical-debt")
def api_technical_debt_trend() -> list[dict[str, Any]]:
    return stats_service().technical_debt_trend()


@app.get("/api/stats/trends/architecture-risk")
def api_architecture_risk_trend() -> list[dict[str, Any]]:
    return stats_service().architecture_risk_trend()


@app.get("/api/stats/team")
def api_team_stats() -> dict[str, Any]:
    return stats_service().team_stats()


@app.get("/api/audit/network")
def api_network_audit(limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
    return repository().list_network_audit(limit=limit, offset=offset)


@app.get("/api/audit/network/{audit_id}")
def api_network_audit_detail(audit_id: int) -> dict[str, Any]:
    record = repository().get_network_audit(audit_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Network audit record not found.")
    return record


@app.get("/api/settings/models")
def api_model_settings() -> dict[str, Any]:
    return model_settings_repository().get().to_safe_dict()


@app.post("/api/settings/models")
async def api_save_model_settings(request: Request) -> dict[str, Any]:
    return model_settings_repository().save(await _request_payload(request)).to_safe_dict()


@app.post("/api/settings/models/test")
async def api_test_model_settings(request: Request) -> dict[str, Any]:
    payload = await _request_payload(request)
    settings = model_settings_repository().save(payload) if payload else model_settings_repository().get()
    return ModelProviderTester().test(settings)


@app.delete("/api/settings/models/api-key")
def api_clear_model_api_key() -> dict[str, Any]:
    return model_settings_repository().clear_api_key().to_safe_dict()


@app.get("/api/review/options")
def api_review_options() -> dict[str, Any]:
    return {
        "max_upload_bytes": max_upload_bytes(),
        "providers": ["none", "mock", "openai", "anthropic", "azure_openai", "openai_compatible", "ollama", "enterprise_gateway"],
        "code_sharing_modes": ["none", "summary_only", "snippets", "full_context"],
    }


@app.post("/api/review/diff")
async def api_review_diff(request: Request) -> dict[str, Any]:
    payload = await _request_payload(request)
    response = hosted_review_service().review_diff(str(payload.get("diff_text", "")), payload)
    return _hosted_response(response)


@app.post("/api/review/project")
async def api_review_project(request: Request) -> dict[str, Any]:
    payload = await _request_payload(request)
    response = hosted_review_service().review_project(str(payload.get("project_path", "")), payload)
    return _hosted_response(response)


@app.post("/api/review/github-pr")
async def api_review_github_pr(request: Request) -> dict[str, Any]:
    payload = await _request_payload(request)
    response = hosted_review_service().review_github_pr(str(payload.get("pr_url", "")), payload)
    return _hosted_response(response)


@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_index(request: Request) -> Any:
    if request is None:
        return "<h1>ReviewAgent Dashboard</h1>"
    if templates is None:
        return HTMLResponse("<h1>ReviewAgent Dashboard</h1>")
    return template_response("index.html", request, {"overview": stats_service().overview()})


@app.get("/projects", response_class=HTMLResponse)
def dashboard_projects(request: Request) -> Any:
    if request is None:
        return "<h1>Projects</h1>"
    if templates is None:
        return HTMLResponse("<h1>Projects</h1>")
    return template_response("projects.html", request, {"projects": repository().list_projects()})


@app.get("/projects/{project_id}", response_class=HTMLResponse)
def dashboard_project_detail(request: Request, project_id: int) -> Any:
    repo = repository()
    project = repo.get_project(project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found.")
    if request is None:
        return f"<h1>{project['name']}</h1>"
    if templates is None:
        return HTMLResponse(f"<h1>{project['name']}</h1>")
    return template_response("project_detail.html", request, {"project": project, "reviews": repo.list_reviews(project_id=project_id)})


@app.get("/reviews/{review_run_id}", response_class=HTMLResponse)
def dashboard_review_detail(request: Request, review_run_id: int) -> Any:
    repo = repository()
    review = repo.get_review_run(review_run_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review run not found.")
    if request is None:
        return f"<h1>Review #{review['id']}</h1>"
    if templates is None:
        return HTMLResponse(f"<h1>Review #{review['id']}</h1>")
    return template_response("review_detail.html", request, {"review": review, "issues": repo.get_review_issues(review_run_id)})


@app.get("/audit/network", response_class=HTMLResponse)
def dashboard_network_audit(request: Request) -> Any:
    records = repository().list_network_audit(limit=200)
    if request is None:
        return "<h1>Network Audit</h1>"
    if templates is None:
        return HTMLResponse("<h1>Network Audit</h1>")
    return template_response("network_audit.html", request, {"records": records})


@app.get("/review", response_class=HTMLResponse)
def dashboard_review_center(request: Request) -> Any:
    if request is None:
        return "<h1>Review Center</h1>"
    return template_response("review/index.html", request, {})


@app.get("/review/diff", response_class=HTMLResponse)
def dashboard_review_diff(request: Request, error: str | None = None) -> Any:
    return template_response("review/diff.html", request, {"error": error or "", "max_upload_bytes": max_upload_bytes()})


@app.post("/review/diff", response_class=HTMLResponse)
async def dashboard_submit_diff_review(request: Request) -> Any:
    payload = await _request_payload(request)
    uploaded = payload.pop("diff_file_content", "")
    if uploaded:
        payload["diff_text"] = uploaded
    response = hosted_review_service().review_diff(str(payload.get("diff_text", "")), payload)
    return _hosted_redirect_or_render(request, response, "review/diff.html")


@app.get("/review/project", response_class=HTMLResponse)
def dashboard_review_project(request: Request, error: str | None = None) -> Any:
    return template_response("review/project.html", request, {"error": error or ""})


@app.post("/review/project", response_class=HTMLResponse)
async def dashboard_submit_project_review(request: Request) -> Any:
    payload = await _request_payload(request)
    response = hosted_review_service().review_project(str(payload.get("project_path", "")), payload)
    return _hosted_redirect_or_render(request, response, "review/project.html")


@app.get("/review/github-pr", response_class=HTMLResponse)
def dashboard_review_github_pr(request: Request, error: str | None = None) -> Any:
    return template_response("review/github_pr.html", request, {"error": error or ""})


@app.post("/review/github-pr", response_class=HTMLResponse)
async def dashboard_submit_github_pr_review(request: Request) -> Any:
    payload = await _request_payload(request)
    response = hosted_review_service().review_github_pr(str(payload.get("pr_url", "")), payload)
    return _hosted_redirect_or_render(request, response, "review/github_pr.html")


@app.get("/review/result", response_class=HTMLResponse)
def dashboard_review_result(request: Request) -> Any:
    return template_response("review/result.html", request, {"result": {"issues": [], "summary": {}}, "error": "Temporary result is no longer available."})


@app.get("/settings/models", response_class=HTMLResponse)
def dashboard_model_settings(request: Request, saved: str | None = None, test: str | None = None) -> Any:
    settings = model_settings_repository().get()
    if request is None:
        return "<h1>Model Provider Settings</h1>"
    if templates is None:
        return HTMLResponse("<h1>Model Provider Settings</h1>")
    return template_response(
        "model_settings.html",
        request,
        {"settings": settings.to_safe_dict(), "saved": saved == "1", "test_result": test or ""},
    )


@app.post("/settings/models", response_class=HTMLResponse)
async def dashboard_save_model_settings(request: Request) -> Any:
    payload = await _request_payload(request)
    action = payload.pop("action", "save")
    repo = model_settings_repository()
    if action == "clear_api_key":
        repo.clear_api_key()
        return RedirectResponse("/settings/models?saved=1", status_code=303)
    settings = repo.save(payload)
    if action == "test":
        result = ModelProviderTester().test(settings)
        status = "ok" if result.get("ok") else "failed"
        return RedirectResponse(f"/settings/models?test={status}", status_code=303)
    return RedirectResponse("/settings/models?saved=1", status_code=303)


async def _request_payload(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            payload = await request.json()
            return dict(payload) if isinstance(payload, dict) else {}
        except Exception:
            return {}
    if "multipart/form-data" in content_type:
        form = await request.form()
        payload: dict[str, Any] = {}
        for key, value in form.multi_items():
            if hasattr(value, "read"):
                content = await value.read()
                if len(content) > max_upload_bytes():
                    payload["diff_file_content"] = ""
                    payload["upload_error"] = "Uploaded diff exceeds the maximum upload size."
                else:
                    try:
                        payload["diff_file_content"] = content.decode("utf-8")
                    except UnicodeDecodeError:
                        payload["diff_file_content"] = ""
                        payload["upload_error"] = "Uploaded diff must be UTF-8 text."
            else:
                payload[key] = str(value)
        for checkbox in ("enabled", "allow_network", "allow_llm", "audit_enabled", "enable_llm", "enable_agents", "enable_enterprise_rules", "save_result"):
            payload[checkbox] = checkbox in form
        return payload
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    payload = {key: values[-1] if values else "" for key, values in form.items()}
    for checkbox in ("enabled", "allow_network", "allow_llm", "audit_enabled", "enable_llm", "enable_agents", "enable_enterprise_rules", "save_result"):
        payload[checkbox] = checkbox in form
    return payload


def _hosted_response(response: Any) -> dict[str, Any]:
    if not response.ok:
        return {"ok": False, "error": response.error, "result": response.result}
    return {"ok": True, "review_run_id": response.review_run_id, "result": response.result}


def _hosted_redirect_or_render(request: Request, response: Any, form_template: str) -> Any:
    if response.ok and response.review_run_id:
        return RedirectResponse(f"/reviews/{response.review_run_id}", status_code=303)
    if response.ok:
        return template_response("review/result.html", request, {"result": response.result, "error": ""})
    return template_response(form_template, request, {"error": response.error, "max_upload_bytes": max_upload_bytes()}, status_code=400)


def main() -> None:
    init_db()
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise SystemExit("uvicorn is required to run the dashboard.") from exc
    host, port = dashboard_host_port()
    uvicorn.run("reviewagent.dashboard.app:app", host=host, port=port)


if __name__ == "__main__":
    main()
