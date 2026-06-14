import json
import subprocess
import sys
from pathlib import Path

from app.architecture import ArchitectureContextBuilder, ArchitectureReviewer
from app.llm.mock_provider import MockLLMProvider
from app.llm.provider import LLMProvider
from app.models.issue import Issue
from app.reviewer import ReviewService
from magicreview.mcp_server import tools


def test_context_builder_extracts_project_summaries_and_static_issues(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "api.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter()\n@router.get('/x')\ndef x():\n    return {'x': 1}\n",
        encoding="utf-8",
    )
    static_issue = Issue(
        severity="medium",
        type="CyclomaticComplexity",
        file="app/api.py",
        line=4,
        message="Function has high cyclomatic complexity.",
        suggestion="Split it.",
    )

    context = ArchitectureContextBuilder(max_context_chars=1000).build(tmp_path, [static_issue])

    assert "app.api" in context.modules
    assert context.functions_summary[0]["name"] == "x"
    assert context.routes_summary[0]["function"] == "x"
    assert context.static_issues_summary[0]["type"] == "CyclomaticComplexity"


def test_context_builder_truncates_large_context(tmp_path: Path) -> None:
    (tmp_path / "big.py").write_text("\n".join(f"def f_{i}():\n    return {i}" for i in range(80)), encoding="utf-8")

    context = ArchitectureContextBuilder(max_context_chars=500).build(tmp_path)
    text = context.to_prompt_text(500)

    assert "TRUNCATED" in text or context.truncated


def test_architecture_prompt_contains_required_constraints(tmp_path: Path) -> None:
    context = ArchitectureContextBuilder().build(tmp_path)
    prompt = ArchitectureReviewer.render_prompt(context.to_prompt_text())

    assert "Return only JSON" in prompt
    assert "severity must be one of: critical, high, medium, low" in prompt
    assert "Do not invent files" in prompt


def test_architecture_reviewer_parses_markdown_and_dedupes(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "service.py").write_text("class UserService:\n    pass\n", encoding="utf-8")
    response = """```json
{"issues": [
  {"severity": "medium", "type": "MaintainabilityRisk", "file": "app/service.py", "line": 1, "message": "Service drift.", "suggestion": "Split responsibilities."},
  {"severity": "medium", "type": "MaintainabilityRisk", "file": "app/service.py", "line": 1, "message": "Service drift.", "suggestion": "Split responsibilities."},
  {"severity": "urgent", "type": "Bad", "file": "app/service.py", "line": 1, "message": "Bad.", "suggestion": "Bad."},
  {"severity": "low", "type": "Missing", "file": "missing.py", "line": 1, "message": "Bad.", "suggestion": "Bad."}
]}
```"""

    issues = ArchitectureReviewer(provider=MockLLMProvider(response)).review_project(tmp_path)

    assert len(issues) == 1
    assert issues[0].type == "MaintainabilityRisk"


def test_architecture_reviewer_handles_invalid_json_and_provider_errors(tmp_path: Path) -> None:
    class FailingProvider(LLMProvider):
        def complete(self, prompt: str) -> str:
            raise RuntimeError("boom")

    invalid = ArchitectureReviewer(provider=MockLLMProvider("not json")).review_project(tmp_path)
    failed = ArchitectureReviewer(provider=FailingProvider()).review_project(tmp_path)

    assert invalid[0].type == "ArchitectureReviewError"
    assert failed[0].type == "ArchitectureReviewError"


def test_review_service_llm_disabled_and_enabled(tmp_path: Path) -> None:
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "services.py").write_text("class UserService:\n    pass\n", encoding="utf-8")
    provider = MockLLMProvider(
        json.dumps(
            {
                "issues": [
                    {
                        "severity": "medium",
                        "type": "MaintainabilityRisk",
                        "file": "app/services.py",
                        "line": 1,
                        "message": "Service has unclear boundaries.",
                        "suggestion": "Split service responsibilities.",
                    }
                ]
            }
        )
    )
    service = ReviewService(architecture_reviewer=ArchitectureReviewer(provider=provider))

    no_llm = service.review_project(str(tmp_path), enable_llm=False)
    with_llm = service.review_project(str(tmp_path), enable_llm=True)

    assert provider.calls
    assert "MaintainabilityRisk" not in {issue["type"] for issue in no_llm["issues"]}
    assert "MaintainabilityRisk" in {issue["type"] for issue in with_llm["issues"]}


def test_cli_project_llm_mock_returns_architecture_issue() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "magicreview.cli.main",
            "project",
            "examples/architecture_bad_project",
            "--llm",
            "--llm-provider",
            "mock",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert "MaintainabilityRisk" in {issue["type"] for issue in payload["issues"]}


def test_mcp_project_llm_parameter_returns_architecture_issue() -> None:
    result = tools.review_project("examples/architecture_bad_project", enable_llm=True, llm_provider="mock")

    assert "MaintainabilityRisk" in {issue["type"] for issue in result["issues"]}
