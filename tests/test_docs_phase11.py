import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_required_project_docs_exist_and_are_non_empty() -> None:
    required = [
        "README.md",
        "CHANGELOG.md",
        "LICENSE",
        "docs/index.md",
        "docs/deployment.md",
        "docs/docker.md",
        "docs/auth.md",
        "docs/model_providers.md",
        "docs/self_hosting.md",
        "docs/privacy.md",
        "docs/public_beta.md",
        "docs/github_app.md",
        "docs/mcp.md",
        "docs/dashboard.md",
        "docs/connected_services.md",
        "docs/hosted_review.md",
        "docs/cli.md",
        "docs/release.md",
    ]
    for relative in required:
        path = ROOT / relative
        assert path.exists(), f"Missing required doc: {relative}"
        assert path.read_text(encoding="utf-8").strip(), f"Empty required doc: {relative}"


def test_readme_has_ci_relevant_product_boundaries() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for expected in [
        "MagicReview",
        "Review code like magic.",
        "local-first",
        "offline",
        "Does not call real LLM providers by default",
            "mgreview",
            "MGREVIEW_",
        "Docker",
        "Dashboard",
        "MCP",
        "GitHub App",
    ]:
        assert expected in readme


def test_command_migration_docs_do_not_promote_legacy_cli() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    cli_doc = (ROOT / "docs" / "cli.md").read_text(encoding="utf-8")
    dashboard_doc = (ROOT / "docs" / "dashboard.md").read_text(encoding="utf-8")
    model_doc = (ROOT / "docs" / "model_providers.md").read_text(encoding="utf-8")
    privacy_doc = (ROOT / "docs" / "privacy.md").read_text(encoding="utf-8")
    docker_doc = (ROOT / "docs" / "docker.md").read_text(encoding="utf-8")

    assert "MagicReview" in readme
    assert "mgreview" in readme
    assert "ReviewAgent compatibility" not in readme
    assert "compatibility shim" not in readme
    assert "REVIEWAGENT_" not in readme
    assert ".reviewagent" not in readme
    assert "`review` CLI" not in cli_doc
    assert not re.search(r"(?m)^review dashboard\b", dashboard_doc)
    assert not re.search(r"(?m)^review project \. --llm\b", model_doc)
    assert not re.search(r"(?m)^review project \. --llm\b", privacy_doc)
    assert "docker run --rm " in docker_doc
    assert not re.search(r"docker run --rm .* MagicReview", docker_doc)
