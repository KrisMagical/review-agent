from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_11_7_required_docs_exist() -> None:
    required = [
        "README.md",
        "docs/deployment.md",
        "docs/docker.md",
        "docs/auth.md",
        "docs/model_providers.md",
        "docs/self_hosting.md",
        "docs/privacy.md",
        "docs/index.md",
        "docs/github_app.md",
        "docs/mcp.md",
        "docs/dashboard.md",
        "docs/connected_services.md",
        "docs/hosted_review.md",
        "docs/release.md",
        "docs/cli.md",
    ]
    for relative in required:
        path = ROOT / relative
        assert path.exists(), f"Missing documentation file: {relative}"
        assert path.read_text(encoding="utf-8").strip(), f"Empty documentation file: {relative}"


def test_readme_documents_offline_defaults_and_entrypoints() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for expected in [
        "local-first",
        "Does not call real LLM providers by default",
        "mgreview --help",
        "mgreview-mcp",
        "mgreview-dashboard",
        "mgreview-github-app",
        "docker compose up dashboard",
        "full_project",
    ]:
        assert expected in readme


def test_docs_explain_network_boundaries() -> None:
    privacy = (ROOT / "docs/privacy.md").read_text(encoding="utf-8")
    connected = (ROOT / "docs/connected_services.md").read_text(encoding="utf-8")
    assert "does not upload source code" in privacy
    assert "NetworkPolicy" in connected
    assert "summary_only" in privacy
    assert "full_project" in privacy
