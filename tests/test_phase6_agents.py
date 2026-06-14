import json
import subprocess
import sys
from pathlib import Path

from app.agents import (
    AgentContext,
    AgentResult,
    ArchitectureAgent,
    BugAgent,
    KnowledgeAgent,
    QualityAgent,
    RefactorAgent,
    BaseAgent,
    ReviewCoordinator,
    SecurityAgent,
)
from app.models.issue import Issue
from app.reviewer import ReviewService
from magicreview.mcp_server import tools


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_agent_context_and_result_are_serializable(tmp_path: Path) -> None:
    context = AgentContext(project_root=tmp_path, files=[Path("a.py")])
    result = AgentResult(
        agent_name="test",
        issues=[
            Issue(
                severity="low",
                type="Example",
                file="a.py",
                line=1,
                message="example",
                suggestion="example",
            )
        ],
    )

    assert context.project_root == tmp_path
    json.dumps(result.to_dict())


class GoodAgent(BaseAgent):
    name = "quality"
    category = "test"

    def run(self, context: AgentContext) -> AgentResult:
        return AgentResult(
            agent_name=self.name,
            issues=[
                Issue(
                    severity="medium",
                    type="Duplicate",
                    file="a.py",
                    line=2,
                    message="same",
                    suggestion="ok",
                ),
                Issue(
                    severity="medium",
                    type="Duplicate",
                    file="a.py",
                    line=2,
                    message="same",
                    suggestion="ok",
                ),
            ],
        )


class FailingAgent(BaseAgent):
    name = "bug"
    category = "test"

    def run(self, context: AgentContext) -> AgentResult:
        raise RuntimeError("boom")


def test_coordinator_aggregates_dedupes_sorts_and_catches_agent_errors(tmp_path: Path) -> None:
    coordinator = ReviewCoordinator([GoodAgent(), FailingAgent()])
    context = AgentContext(project_root=tmp_path)

    result = coordinator.review_project(tmp_path, context=context, selected_agents=["quality", "bug", "missing"])
    types = [issue["type"] for issue in result["issues"]]

    assert types == ["Duplicate", "AgentExecutionError", "UnknownAgent"]


def test_quality_agent_reuses_quality_rules(tmp_path: Path) -> None:
    source = "def too_long(a):\n" + "\n".join("    x = 1" for _ in range(82)) + "\n    return a\n"
    write(tmp_path / "bad.py", source)
    context = AgentContext(project_root=tmp_path, files=[Path("bad.py")])

    issues = QualityAgent().run(context).issues

    assert any(issue.type == "FunctionTooLongRule" for issue in issues)
    assert any(issue.type == "TypeHintRule" for issue in issues)


def test_bug_agent_returns_existing_and_lightweight_bug_risks(tmp_path: Path) -> None:
    write(
        tmp_path / "buggy.py",
        "def run(data, items=[]):\n"
        "    value = data.get('x')\n"
        "    print(value.name)\n"
        "    missing = data['missing']\n"
        "    try:\n"
        "        return missing / data['count']\n"
        "    except:\n"
        "        return items[0]\n",
    )
    context = AgentContext(project_root=tmp_path, files=[Path("buggy.py")])

    types = {issue.type for issue in BugAgent().run(context).issues}

    assert "NoneRiskRule" in types
    assert "KeyErrorRule" in types
    assert "MutableDefaultArgumentRisk" in types
    assert "BroadExceptionRisk" in types


def test_architecture_agent_static_and_mock_llm(tmp_path: Path) -> None:
    write(tmp_path / "a.py", "import b\n")
    write(tmp_path / "b.py", "import a\n")
    write(tmp_path / "app/services/user_service.py", "def run():\n    return 1\n")
    context = AgentContext(project_root=tmp_path, files=[Path("a.py"), Path("b.py")])

    static_types = {issue.type for issue in ArchitectureAgent().run(context).issues}
    assert "CircularDependency" in static_types
    assert "ArchitectureReviewError" not in static_types

    llm_context = AgentContext(project_root=tmp_path, files=[Path("a.py"), Path("b.py")], enable_llm=True, llm_provider="mock")
    llm_types = {issue.type for issue in ArchitectureAgent().run(llm_context).issues}
    assert "MaintainabilityRisk" in llm_types


def test_security_agent_detects_security_risks(tmp_path: Path) -> None:
    write(
        tmp_path / "security.py",
        "import os\n"
        "SECRET_KEY = 'secret'\n"
        "API_KEY = 'hardcoded'\n"
        "def run(cursor, user_id, path, command):\n"
        "    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n"
        "    open(path).read()\n"
        "    os.system(command)\n",
    )
    context = AgentContext(project_root=tmp_path, files=[Path("security.py")])

    types = {issue.type for issue in SecurityAgent().run(context).issues}

    assert "SQLInjectionRule" in types
    assert "PathTraversalRule" in types
    assert "HardcodedSecretRisk" in types
    assert "JWTWeakSecretRisk" in types
    assert "CommandInjectionRisk" in types


def test_knowledge_agent_loads_enterprise_config_and_no_config_is_safe(tmp_path: Path) -> None:
    write(
        tmp_path / "magicreview.yml",
        "rules:\n"
        "  max_parameters:\n"
        "    enabled: true\n"
        "    max_params: 1\n"
        "    severity: medium\n",
    )
    write(tmp_path / "app.py", "def run(a, b):\n    return a + b\n")

    context = AgentContext(project_root=tmp_path, files=[Path("app.py")])
    assert any(issue.type == "EnterpriseMaxParameters" for issue in KnowledgeAgent().run(context).issues)

    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    assert KnowledgeAgent().run(AgentContext(project_root=empty_root)).issues == []


def test_refactor_agent_generates_suggestions_without_writing_files(tmp_path: Path) -> None:
    source_file = write(tmp_path / "app.py", "def run():\n    return 1\n")
    context = AgentContext(
        project_root=tmp_path,
        static_issues=[
            Issue(
                severity="high",
                type="GodClass",
                file="app.py",
                line=1,
                message="large",
                suggestion="split",
            )
        ],
    )

    issues = RefactorAgent().run(context).issues

    assert issues[0].type == "SplitModuleSuggestion"
    assert source_file.read_text(encoding="utf-8") == "def run():\n    return 1\n"


def test_review_service_agents_and_subset_selection(tmp_path: Path) -> None:
    write(tmp_path / "bad.py", "import os\nAPI_KEY = 'hardcoded'\ndef run(a):\n    return a + 42\n")
    service = ReviewService()

    normal = service.review_project(str(tmp_path), enable_agents=False)
    agent_result = service.review_project(str(tmp_path), enable_agents=True, agents=["security"])

    assert "issues" in normal
    agent_types = {issue["type"] for issue in agent_result["issues"]}
    assert "HardcodedSecretRisk" in agent_types
    assert "TypeHintRule" not in agent_types


def test_cli_agents_return_json(tmp_path: Path) -> None:
    write(tmp_path / "bad.py", "import os\nAPI_KEY = 'hardcoded'\ndef run(a):\n    return a + 42\n")

    all_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path), "--agents"],
        check=True,
        capture_output=True,
        text=True,
    )
    subset_result = subprocess.run(
        [sys.executable, "-m", "magicreview.cli.main", "project", str(tmp_path), "--agents", "quality,security"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "issues" in json.loads(all_result.stdout)
    assert "issues" in json.loads(subset_result.stdout)


def test_mcp_review_project_supports_agents(tmp_path: Path) -> None:
    write(tmp_path / "bad.py", "API_KEY = 'hardcoded'\n")

    result = tools.review_project(str(tmp_path), enable_agents=True, agents=["security"])

    assert any(issue["type"] == "HardcodedSecretRisk" for issue in result["issues"])
    json.dumps(result)
