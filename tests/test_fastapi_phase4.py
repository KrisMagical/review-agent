import ast
from pathlib import Path

from app.analyzers.fastapi import (
    FastAPIDependencyAnalyzer,
    FastAPIDetector,
    FastAPIProjectAnalyzer,
    FastAPIRouteAnalyzer,
    PydanticModelAnalyzer,
)
from app.reviewer import ReviewService
from magicreview.mcp_server import tools


def parse(source: str) -> ast.AST:
    return ast.parse(source)


def issue_types(issues) -> set[str]:
    return {issue.type if hasattr(issue, "type") else issue["type"] for issue in issues}


def test_fastapi_detector_identifies_app_router_and_ignores_plain_python() -> None:
    detector = FastAPIDetector()

    assert detector.is_fastapi_source("from fastapi import FastAPI\napp = FastAPI()\n")
    assert detector.is_fastapi_source("from fastapi import APIRouter\nrouter = APIRouter()\n")
    assert not detector.is_fastapi_source("def run() -> int:\n    return 1\n")


def test_fastapi_route_analyzer_flags_api_design_issues() -> None:
    source = """
from fastapi import APIRouter
router = APIRouter()

@router.post("/users")
def create_user(payload):
    session.execute("select 1")
    if payload:
        if payload.get("active"):
            if payload.get("admin"):
                return {"id": 1}
    return {"id": 2}
"""

    issues = FastAPIRouteAnalyzer().analyze_tree(parse(source), "routers/user.py")

    assert {
        "FastAPIMissingResponseModel",
        "FastAPIMissingStatusCode",
        "FastAPIUnstructuredResponse",
        "FastAPIHeavyRouteHandler",
    }.issubset(issue_types(issues))


def test_pydantic_analyzer_flags_schema_risks() -> None:
    source = """
from typing import Optional
from pydantic import BaseModel

class UserCreateRequest(BaseModel):
    username: str
    nickname: Optional[str]
    tags: list[str] = []
    metadata = {}
"""

    issues = PydanticModelAnalyzer().analyze_tree(parse(source), "schemas.py")

    assert {
        "PydanticMissingFieldValidation",
        "PydanticOptionalFieldRisk",
        "PydanticMutableDefault",
        "PydanticMissingTypeAnnotation",
    }.issubset(issue_types(issues))


def test_dependency_analyzer_flags_di_risks() -> None:
    source = """
from fastapi import APIRouter, Depends
router = APIRouter()

def get_db():
    db = SessionLocal()
    return db

@router.get("/users")
def list_users(db=Depends(lambda: SessionLocal()), client=Depends(get_db)):
    session = SessionLocal()
    service = UserService()
    return {"id": 1}
"""

    issues = FastAPIDependencyAnalyzer().analyze_tree(parse(source), "routers/user.py")

    assert {
        "FastAPIMissingDependencyInjection",
        "FastAPIComplexDepends",
        "FastAPIResourceDependencyRisk",
    }.issubset(issue_types(issues))


def test_fastapi_project_analyzer_runs_only_for_fastapi_projects(tmp_path: Path) -> None:
    (tmp_path / "plain.py").write_text("def run() -> int:\n    return 1\n", encoding="utf-8")
    assert FastAPIProjectAnalyzer().analyze_project(tmp_path) == []

    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n@app.get('/x')\ndef x():\n    return {'x': 1}\n",
        encoding="utf-8",
    )
    issues = FastAPIProjectAnalyzer().analyze_project(tmp_path)
    assert any(issue.type.startswith("FastAPI") for issue in issues)


def test_review_project_and_mcp_return_fastapi_issues() -> None:
    result = ReviewService().review_project("examples/fastapi_bad_project")
    types = {issue["type"] for issue in result["issues"]}

    assert "FastAPIMissingResponseModel" in types
    assert "PydanticMutableDefault" in types
    assert "FastAPIComplexDepends" in types

    mcp_result = tools.review_project("examples/fastapi_bad_project")
    assert "FastAPIMissingResponseModel" in {issue["type"] for issue in mcp_result["issues"]}


def test_non_fastapi_project_has_no_fastapi_issues() -> None:
    result = ReviewService().review_project("examples/phase2_bad_project")

    assert not any(issue["type"].startswith("FastAPI") or issue["type"].startswith("Pydantic") for issue in result["issues"])
