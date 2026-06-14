# Docker

MagicReview includes a Dockerfile and Docker Compose setup for local and self-hosted use.

## Build Image

```bash
docker build -t magicreview .
```

The image uses Python 3.12 slim, installs MagicReview with runtime extras, creates a non-root user, and uses `/data` for SQLite persistence.

## Run CLI In Docker

```bash
docker run --rm magicreview mgreview --help
docker run --rm magicreview mgreview --version
docker run --rm magicreview python -m magicreview.cli.main --help
```

## Review Local Project With Volume Mount

Windows PowerShell:

```powershell
docker run --rm -v "${PWD}:/workspace" magicreview mgreview project /workspace --format json
```

Linux/macOS:

```bash
docker run --rm -v "$PWD:/workspace" magicreview mgreview project /workspace --format json
```

The container reads the mounted project. It does not execute reviewed code.

## Run Dashboard

```bash
docker run --rm -p 8080:8080 -v "$PWD/.magicreview:/data" magicreview mgreview-dashboard
```

Or:

```bash
docker run --rm -p 8080:8080 -v "$PWD/.magicreview:/data" magicreview mgreview dashboard serve --host 0.0.0.0 --port 8080
```

Open:

```text
http://127.0.0.1:8080
```

## Run GitHub App

```bash
docker run --rm -p 8000:8000 --env-file .env -v "$PWD/.magicreview:/data" magicreview mgreview-github-app
```

Open:

```text
http://127.0.0.1:8000/health
```

Webhook review requires GitHub App credentials in `.env`.

## Run MCP In Docker

```bash
docker run --rm -i magicreview mgreview-mcp
```

MCP uses stdio. Docker MCP is mainly for advanced local integration.

## Docker Compose

```bash
docker compose config
docker compose up dashboard
docker compose up github-app
docker compose up
```

Services:

- `dashboard`: Dashboard on port `8080`
- `github-app`: GitHub webhook server on port `8000`
- `mcp`: optional stdio service

## Volumes

Compose mounts:

- `./.magicreview:/data` for SQLite
- `./:/workspace:ro` for hosted project review

The `.magicreview` directory contains local Dashboard data and should be backed up if you rely on historical reports.

## .env Configuration

Start from:

```bash
cp .env.example .env
```

Do not commit `.env`.

Key sections:

- Dashboard
- Database
- Auth
- GitHub App
- Model providers
- Network policy
- Hosted Review Web UI

## Health Checks

Dashboard:

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8080/health').read().decode())"
```

GitHub App:

```bash
python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health').read().decode())"
```

Compose health checks use the same endpoints. Health checks do not require LLM or GitHub credentials.

## Offline Behavior

Docker defaults are offline:

- provider defaults to `none`
- NetworkPolicy defaults to disabled
- real LLM calls are blocked unless explicitly allowed
- GitHub App only calls GitHub when processing webhook or explicit PR review flows

## LLM / Network Behavior

To use a real provider, configure API keys and explicit policy:

```bash
MGREVIEW_LLM_PROVIDER=openai
OPENAI_API_KEY=...
MGREVIEW_NETWORK_ENABLED=true
MGREVIEW_ALLOW_LLM=true
MGREVIEW_CODE_SHARING_MODE=summary_only
```

CLI real-provider example:

```bash
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

## GitHub Review Modes

```bash
MGREVIEW_GITHUB_REVIEW_MODE=diff_only
MGREVIEW_GITHUB_REVIEW_MODE=full_project
```

`full_project` fetches Python/config/limited metadata files for the PR head commit using GitHub Trees/Blob APIs. It is not a full repository mirror and skips secret-like files.

## Troubleshooting Docker Hub Timeout

If pulling `python:3.12-slim` times out:

```bash
docker pull python:3.12-slim
```

or configure your Docker registry mirror. Then rebuild:

```bash
docker build -t magicreview .
```

## Security Notes

- `.env` is excluded from the image and should never be committed.
- `.magicreview` is excluded from the image and used as a local volume.
- Run Dashboard behind auth before server/public exposure.
- Use HTTPS, VPN, Tailscale, WireGuard, or Cloudflare Tunnel for remote access.




