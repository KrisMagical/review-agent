# ReviewAgent

ReviewAgent is a local-first, self-hostable, agent-native code review platform for static analysis, enterprise rules, optional LLM review, GitHub PR review, MCP integration, and governance dashboards.

It is designed for developers and teams that want useful review automation without giving up control of code, credentials, or deployment.

## What Is ReviewAgent?

ReviewAgent reviews Python code through multiple entry points:

- Local CLI: `review file`, `review diff`, and `review project`
- MCP stdio server for AI coding tools
- GitHub App webhook review for pull requests
- Web Dashboard for review history, trends, model settings, and hosted review
- Enterprise YAML/JSON rules
- Optional LLM architecture review
- Optional multi-agent review

All findings use the same JSON issue shape:

```json
{
  "issues": [
    {
      "severity": "high",
      "type": "ExampleIssue",
      "file": "app/main.py",
      "line": 12,
      "message": "What ReviewAgent found.",
      "suggestion": "How to improve it."
    }
  ]
}
```

## Why Local-First?

ReviewAgent defaults are intentionally conservative:

- Runs locally by default
- Does not call real LLM providers by default
- Does not upload code by default
- Does not enable network access by default
- Does not modify, commit, push, or execute reviewed code

Networked services require explicit configuration and authorization. Real LLM providers require API keys plus network policy flags such as `--allow-network`, `--allow-llm`, and a non-`none` code sharing mode.

## Feature Overview

- Static review for files, diffs, and projects
- Ruff/Radon-style quality signals, import graph checks, and God Object detection
- FastAPI route, Pydantic, and dependency injection checks
- Enterprise rule center with YAML/JSON policies
- Optional LLM architecture review
- Multi-agent review with quality, bug, architecture, security, knowledge, and refactor agents
- MCP server over stdio
- GitHub App PR review with `diff_only` and optional `full_project` modes
- Dashboard with SQLite persistence, trends, audit records, model settings, and hosted review forms
- Docker and Docker Compose deployment

## Quick Start

From source:

```bash
git clone https://github.com/KrisMagical/review-agent.git
cd review-agent
pip install -e ".[all]"
review --help
review project examples/multi_agent_project --agents --format terminal
```

Mock LLM review stays offline:

```bash
review project . --llm --llm-provider mock
```

Real provider example with explicit network authorization:

```bash
review project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

## Installation

Editable install for development:

```bash
pip install -e ".[all,dev]"
```

Package install, once published:

```bash
pip install reviewagent
```

PyPI publication is reserved for the first package release. Until then, install from source or GitHub Releases.

Installed commands:

```bash
review --help
reviewagent --help
reviewagent-mcp
reviewagent-dashboard
reviewagent-github-app
```

## Local CLI

```bash
review file examples/bad_code.py --format json
cat examples/sample.diff | review diff --format terminal
review diff --file examples/sample.diff --format markdown --output review.md
review project examples/phase2_bad_project --format terminal
review project examples/enterprise_policy_project --config examples/enterprise_policy_project/reviewagent.yml
review project examples/multi_agent_project --agents quality,security --format json
review project . --fail-on high
```

Output formats:

- `json`
- `terminal`
- `markdown`
- `html`

JSON is the default for automation and always includes `issues`.

## Docker Deploy

```bash
docker build -t reviewagent .
docker run --rm reviewagent review --help
docker compose up dashboard
```

Review the current project from Docker:

Windows PowerShell:

```powershell
docker run --rm -v "${PWD}:/workspace" reviewagent review project /workspace --format json
```

Linux/macOS:

```bash
docker run --rm -v "$PWD:/workspace" reviewagent review project /workspace --format json
```

Docker Compose persists SQLite data in `./.reviewagent` and exposes:

- Dashboard: `http://127.0.0.1:8080`
- GitHub App webhook server: `http://127.0.0.1:8000`

See [Docker](docs/docker.md) and [Docker README](docker/README.md).

## Web Dashboard

```bash
review dashboard init-db
review dashboard serve --host 127.0.0.1 --port 8080
```

The Dashboard shows projects, review runs, issues, trends, network audit, model settings, and hosted review pages.

For server deployment, enable authentication and HTTPS:

```bash
REVIEWAGENT_AUTH_ENABLED=true
REVIEWAGENT_ADMIN_USERNAME=admin
REVIEWAGENT_ADMIN_PASSWORD=use-a-strong-password
REVIEWAGENT_SESSION_SECRET=use-a-random-secret
REVIEWAGENT_API_KEYS=use-a-random-api-token
```

Do not expose an unauthenticated Dashboard to the public internet.

## Hosted Review Web UI

Open `/review` in the Dashboard to run reviews without a terminal:

- `/review/diff`: paste a diff or upload a `.diff` / `.patch`
- `/review/project`: review a server-local project path
- `/review/github-pr`: review a GitHub PR URL

Server-local project review is restricted by:

```bash
REVIEWAGENT_ALLOWED_REVIEW_ROOTS=/workspace,/repos
```

Hosted reviews run synchronously in the web request in this phase. They do not execute reviewed code or save uploaded diff content as source artifacts.

## GitHub App

Start the webhook server:

```bash
reviewagent-github-app
```

Required GitHub App settings include:

- `GITHUB_APP_ID`
- `GITHUB_PRIVATE_KEY`
- `GITHUB_WEBHOOK_SECRET`

PR review modes:

- `diff_only`: default, fetches and reviews the PR diff
- `full_project`: fetches Python/config/limited metadata files for the PR head commit through GitHub Trees/Blob APIs, builds a temporary project directory, and runs project review

`full_project` is not a full repository mirror. It skips secrets, enforces file and byte limits, handles truncated Git trees as a safe error, and cleans temporary files.

The GitHub App never auto-fixes, commits, or pushes code.

## MCP Server

Run the local MCP stdio server:

```bash
reviewagent-mcp
```

MCP exposes:

- `review_file(path)`
- `review_diff(diff)`
- `review_project(path, enable_llm=false, enable_agents=false, ...)`

MCP is local stdio by default and does not start an HTTP service.

## LLM Providers

Dashboard model settings are available at `/settings/models`.

Supported provider types:

- `none`
- `mock`
- `openai`
- `anthropic`
- `azure_openai`
- `openai_compatible`
- `ollama`
- `enterprise_gateway`

API keys are masked in UI/API responses. Environment variables are recommended for production and take priority over stored keys.

Stored keys are a local self-hosted convenience and are not encrypted at rest in this phase.

## Enterprise Rules

ReviewAgent can auto-load enterprise policy files:

- `reviewagent.yml`
- `reviewagent.yaml`
- `reviewagent.json`
- `.reviewagent.yml`
- `.reviewagent.yaml`
- `.reviewagent.json`

Example:

```bash
review project examples/enterprise_policy_project --config examples/enterprise_policy_project/reviewagent.yml
```

Rules include max function length, max parameters, forbidden imports, SQL `SELECT *`, controller-to-repository dependency checks, service logging requirements, and layer rules.

## Multi-Agent Review

```bash
review project examples/multi_agent_project --agents
review project examples/multi_agent_project --agents quality,bug,security
```

Agents run synchronously and produce normal issues. They do not modify files.

## Privacy & Network Policy

NetworkPolicy controls connected services:

- `enabled`
- `allow_llm`
- `allow_github_api`
- `allow_remote_mcp`
- `code_sharing_mode`
- `allowed_providers`
- `audit_enabled`

Code sharing modes:

- `none`: send no code or summaries
- `summary_only`: bounded summaries only
- `snippets`: selected snippets may be sent
- `full_context`: larger source context may be sent

Use `summary_only` for external LLM providers unless your organization has approved broader sharing.

See [Privacy](docs/privacy.md) and [Connected Services](docs/connected_services.md).

## Examples

```bash
review file examples/bad_code.py --format terminal
review project examples/fastapi_bad_project --format json
review project examples/architecture_bad_project --llm --llm-provider mock
review project examples/multi_agent_project --agents --save --format json
docker compose up dashboard
```

## Documentation Index

Start with [Documentation Index](docs/index.md).

- [CLI](docs/cli.md)
- [Docker](docs/docker.md)
- [Deployment](docs/deployment.md)
- [Self Hosting](docs/self_hosting.md)
- [Auth](docs/auth.md)
- [Dashboard](docs/dashboard.md)
- [Hosted Review](docs/hosted_review.md)
- [GitHub App](docs/github_app.md)
- [MCP](docs/mcp.md)
- [Model Providers](docs/model_providers.md)
- [Connected Services](docs/connected_services.md)
- [Privacy](docs/privacy.md)
- [Enterprise Rules](docs/enterprise_rules.md)
- [Architecture Review](docs/architecture_review.md)
- [Multi-Agent Review](docs/multi_agent.md)
- [Release](docs/release.md)

## CI / Quality Gate

Local Python quality gate:

```bash
python scripts/quality_gate.py
```

Include Docker checks:

```bash
python scripts/quality_gate.py --docker
```

GitHub Actions validate tests, Ruff lint, package build, Docker build, Compose config, and release artifacts. CI is configured with offline defaults and does not call real LLM providers or GitHub APIs.

## Roadmap

Completed through Phase 11.6:

- Release packaging
- Docker deployment
- Private Dashboard access
- Model provider settings
- Hosted Review Web UI
- GitHub `full_project` review mode

Planned next:

- Documentation quality gate
- More deployment hardening
- Model provider UX refinements
- Optional hosted review workflows

Not currently implemented:

- RBAC
- SSO/SAML/OAuth
- SaaS multi-tenancy
- background queue workers
- automatic code fixes or commits

## Security Notes

- Dashboard auth is disabled by default for local development; enable it before server or public access.
- Use HTTPS, VPN, Tailscale, WireGuard, or Cloudflare Tunnel for private access.
- Keep `.env`, API keys, GitHub private keys, and SQLite backups out of Git.
- GitHub `/webhook` uses GitHub signature verification and is separate from Dashboard login.
- ReviewAgent performs static review and does not execute reviewed code.

## License

ReviewAgent is released under the MIT License. See [LICENSE](LICENSE).
