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
        "local-first",
        "offline",
        "Does not call real LLM providers by default",
        "Docker",
        "Dashboard",
        "MCP",
        "GitHub App",
    ]:
        assert expected in readme
