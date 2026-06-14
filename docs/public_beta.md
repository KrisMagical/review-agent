# Public Beta Guide

MagicReview is ready for public beta evaluation as a local-first, self-hostable code review platform.

## Supported Usage Modes

- Local CLI:
  - `mgreview file`
  - `mgreview diff`
  - `mgreview project`
- Multi-agent project review:
  - `mgreview project . --agents`
- Enterprise YAML/JSON rules:
  - `mgreview project . --config magicreview.yml`
- Optional LLM architecture review:
  - `mgreview project . --llm --llm-provider mock`
  - real providers require explicit network authorization
- MCP stdio server:
  - `mgreview-mcp`
- GitHub App PR review:
  - `diff_only`
  - optional `full_project`
- Dashboard:
  - persisted review history
  - issue trends
  - network audit
  - model settings
  - hosted review pages
- Docker / Docker Compose:
  - Dashboard
  - GitHub App
  - CLI inside container
  - MCP for advanced stdio usage

## Known Limits

- Python-focused review; non-Python analysis is limited.
- Hosted Review Web UI runs synchronously and has no queue/worker yet.
- Dashboard has basic auth/session/Bearer auth, but no RBAC, SSO, or multi-user workspace.
- Model API keys stored in SQLite are masked in UI/API output but are not encrypted at rest.
- Real LLM quality depends on configured provider, model, and code sharing policy.
- GitHub `full_project` mode fetches selected Python/config/metadata files, not a full repository mirror.
- Some static rules may over-report on intentionally dynamic Python, generated code, scripts, or tests.
- Ruff formatting is not enforced as a public beta quality gate.

## Security Boundaries

MagicReview defaults are conservative:

- local-first
- offline by default
- no real LLM calls by default
- no code upload by default
- no automatic code modification
- no automatic commit or push
- no project code execution or import

Enable Dashboard auth before server exposure:

```bash
MGREVIEW_AUTH_ENABLED=true
MGREVIEW_ADMIN_USERNAME=admin
MGREVIEW_ADMIN_PASSWORD=...
MGREVIEW_SESSION_SECRET=...
MGREVIEW_API_KEYS=...
```

Use HTTPS, VPN, Tailscale, WireGuard, or Cloudflare Tunnel for remote access.

## How To Report Issues

When opening an issue, include:

- MagicReview version: `mgreview --version`
- Python version: `python --version`
- OS and shell
- command you ran
- whether Docker was used
- whether `--agents`, `--llm`, or enterprise config was enabled
- sanitized output JSON or terminal report
- minimal reproduction project or diff, if possible

Do not include API keys, GitHub tokens, webhook secrets, private keys, or proprietary source unless you are allowed to share it.

## Bug Report Template

```markdown
## Summary

What happened?

## Expected

What should have happened?

## Command

```bash
mgreview project . --format json
```

## Environment

- MagicReview:
- Python:
- OS:
- Install method:

## Output

Paste sanitized JSON or terminal output.

## Notes

Any config, Docker, Dashboard, GitHub App, or LLM details.
```

## How To Contribute Rules

Good rule contributions should include:

- rule purpose
- exact issue type
- severity rationale
- example bad code
- example good code
- tests for true positives
- tests for non-issues
- documentation update if user-facing

Enterprise rules can often start as YAML/JSON policy examples before becoming built-in checks.

## Docker Deployment

Build:

```bash
docker build -t magicreview .
```

Run CLI:

```bash
docker run --rm magicreview mgreview --help
```

Review current project:

Windows PowerShell:

```powershell
docker run --rm -v "${PWD}:/workspace" magicreview mgreview project /workspace --format json
```

Linux/macOS:

```bash
docker run --rm -v "$PWD:/workspace" magicreview mgreview project /workspace --format json
```

Run Dashboard:

```bash
docker compose up dashboard
```

Run GitHub App:

```bash
docker compose up github-app
```

Do not commit `.env`; use `.env.example` as a starting point.

## Enable LLM Review

Offline mock provider:

```bash
mgreview project . --llm --llm-provider mock
```

Real provider example:

```bash
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

Environment example:

```bash
MGREVIEW_LLM_PROVIDER=openai
OPENAI_API_KEY=...
MGREVIEW_NETWORK_ENABLED=true
MGREVIEW_ALLOW_LLM=true
MGREVIEW_CODE_SHARING_MODE=summary_only
```

Use `summary_only` unless your team has approved broader sharing.

## Disable Network Access

Default:

```bash
MGREVIEW_LLM_PROVIDER=none
MGREVIEW_NETWORK_ENABLED=false
MGREVIEW_ALLOW_LLM=false
MGREVIEW_CODE_SHARING_MODE=none
```

Avoid passing:

- `--allow-network`
- `--allow-llm`
- real provider API keys

For MCP, omit `network_policy` unless networked LLM review is explicitly approved.

## Public Beta Evaluation Checklist

- `pip install -e ".[all,dev]"`
- `pytest --basetemp=.pytest_tmp`
- `mgreview --help`
- `mgreview project . --format terminal`
- `mgreview project . --agents --format json`
- `mgreview project . --llm --llm-provider mock`
- `docker build -t magicreview .`
- `docker compose config`
- Dashboard opens locally
- Hosted Review pages are reachable
- No unexpected network calls occur




