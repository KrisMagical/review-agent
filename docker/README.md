# ReviewAgent Docker Guide

ReviewAgent can run as a local CLI image, Dashboard service, GitHub App webhook service, or MCP stdio server.

ReviewAgent is offline by default. The Docker image does not include `.env`, local databases, API keys, or GitHub private keys.

## Build

```bash
docker build -t reviewagent .
```

## CLI

```bash
docker run --rm reviewagent review --help
docker run --rm reviewagent review --version
docker run --rm -v "$PWD:/workspace" reviewagent review project /workspace --format json
```

On Windows PowerShell:

```powershell
docker run --rm -v "${PWD}:/workspace" reviewagent review project /workspace --format json
```

## Dashboard

```bash
docker run --rm -p 8080:8080 -v "$PWD/.reviewagent:/data" reviewagent reviewagent-dashboard
```

or:

```bash
docker run --rm -p 8080:8080 -v "$PWD/.reviewagent:/data" reviewagent review dashboard serve --host 0.0.0.0 --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

Health check:

```text
http://127.0.0.1:8080/health
```

For server access, enable Dashboard authentication in `.env`:

```bash
REVIEWAGENT_AUTH_ENABLED=true
REVIEWAGENT_ADMIN_USERNAME=admin
REVIEWAGENT_ADMIN_PASSWORD=use-a-strong-password
REVIEWAGENT_SESSION_SECRET=use-a-random-secret
REVIEWAGENT_API_KEYS=use-a-random-api-token
```

Generate random secrets with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## GitHub App

Copy `.env.example` to `.env` and configure the GitHub App values:

```bash
cp .env.example .env
docker run --rm -p 8000:8000 --env-file .env -v "$PWD/.reviewagent:/data" reviewagent reviewagent-github-app
```

Health check:

```text
http://127.0.0.1:8000/health
```

The GitHub App still requires a valid webhook secret, app id, and private key to process webhooks. Missing configuration should not affect Dashboard usage.

## MCP

MCP uses stdio and is mainly for local advanced integrations:

```bash
docker run --rm -i reviewagent reviewagent-mcp
```

## Docker Compose

Start the Dashboard:

```bash
docker compose up dashboard
```

Start the GitHub App:

```bash
docker compose up github-app
```

Start the core web services:

```bash
docker compose up
```

Validate compose configuration:

```bash
docker compose config
```

Run MCP explicitly:

```bash
docker compose --profile mcp run --rm mcp
```

## Persistence

SQLite data is stored in `/data/reviewagent.db` inside the container.

With Docker Compose, `/data` is mounted to:

```text
./.reviewagent
```

Back up this directory if you want to preserve Dashboard history.

## Configuration

Use `.env.example` as the template for `.env`.

Important defaults:

- `REVIEWAGENT_LLM_PROVIDER=none`
- `REVIEWAGENT_NETWORK_ENABLED=false`
- `REVIEWAGENT_ALLOW_LLM=false`
- `REVIEWAGENT_CODE_SHARING_MODE=none`
- `REVIEWAGENT_AUTH_ENABLED=false`

Real LLM providers require explicit API keys and explicit network policy changes. Do not bake secrets into the Docker image.

Model provider settings are also available in the Dashboard at:

```text
http://127.0.0.1:8080/settings/models
```

For host Ollama from Docker Desktop, use:

```bash
REVIEWAGENT_OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Linux hosts may need additional host gateway configuration. See `docs/model_providers.md`.

Hosted Review Web UI is available at:

```text
http://127.0.0.1:8080/review
```

Compose mounts the current repository as read-only `/workspace` and sets:

```bash
REVIEWAGENT_ALLOWED_REVIEW_ROOTS=/workspace
REVIEWAGENT_MAX_UPLOAD_BYTES=5242880
```

Change the mount if you want the Dashboard to review a different server-local
code directory. See `docs/hosted_review.md`.

GitHub PR review can run in `diff_only` or `full_project` mode:

```bash
REVIEWAGENT_GITHUB_REVIEW_MODE=diff_only
# or
REVIEWAGENT_GITHUB_REVIEW_MODE=full_project
```

`full_project` fetches Python/config files for the PR head commit through the
GitHub API and reviews a temporary project directory. It does not enable LLM by
default.

## Security

- The container runs as a non-root user.
- `.env` and `.reviewagent` are excluded from the image build context.
- Dashboard authentication is disabled by default for local development.
- Enable `REVIEWAGENT_AUTH_ENABLED=true` before exposing Dashboard outside your machine or trusted private network.
- Use HTTPS and set `REVIEWAGENT_COOKIE_SECURE=true` for browser access over a real domain.
- See `docs/auth.md` and `docs/deployment.md` for private web access, Nginx, and HTTPS guidance.

## Troubleshooting

- If `docker compose up github-app` starts but webhooks fail, check `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, and `GITHUB_WEBHOOK_SECRET`.
- If Dashboard history disappears, verify the `./.reviewagent:/data` volume mapping.
- If MCP appears idle, remember it is a stdio server waiting for an MCP client.
