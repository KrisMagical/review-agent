# Deployment

This guide summarizes local, Docker, server, Dashboard, GitHub App, and MCP deployment modes.

## Deployment Overview

MagicReview supports:

- Local CLI execution
- Docker image
- Docker Compose for Dashboard and GitHub App
- Self-hosted Dashboard
- GitHub App webhook server
- MCP stdio server for local AI tool integration

Defaults are local-first and offline. Real LLM providers and GitHub API calls require explicit configuration.

## Local Developer Mode

```bash
pip install -e ".[all,dev]"
mgreview --help
mgreview project examples/multi_agent_project --agents --format terminal
```

The local CLI does not start web services and does not require credentials.

## Docker Mode

```bash
docker build -t magicreview .
docker run --rm magicreview mgreview --help
```

Review a local project:

```bash
docker run --rm -v "$PWD:/workspace" magicreview mgreview project /workspace --format json
```

See [Docker](docker.md) for Windows PowerShell examples.

## Docker Compose Mode

```bash
docker compose up dashboard
docker compose up github-app
```

Core services:

- `dashboard`: `http://127.0.0.1:8080`
- `github-app`: `http://127.0.0.1:8000`
- `mcp`: optional stdio service for advanced local integration

SQLite data persists in `./.magicreview` through the `/data` container volume.

## Server Deployment Mode

For a single server:

1. Install Docker and Docker Compose.
2. Copy `.env.example` to `.env`.
3. Set Dashboard auth and GitHub App secrets if needed.
4. Start services with Docker Compose.
5. Put Dashboard behind HTTPS, VPN, Tailscale, WireGuard, or Cloudflare Tunnel.

Do not expose an unauthenticated Dashboard to the public internet.

## Dashboard Deployment

Local:

```bash
mgreview dashboard init-db
mgreview dashboard serve --host 127.0.0.1 --port 8080
```

Docker:

```bash
docker compose up dashboard
```

Important environment variables:

```bash
MGREVIEW_DB_PATH=/data/magicreview.db
MGREVIEW_DASHBOARD_HOST=0.0.0.0
MGREVIEW_DASHBOARD_PORT=8080
MGREVIEW_AUTH_ENABLED=true
MGREVIEW_ADMIN_PASSWORD=...
MGREVIEW_SESSION_SECRET=...
MGREVIEW_API_KEYS=...
```

## GitHub App Deployment

The GitHub App webhook server needs a public webhook URL.

```bash
mgreview-github-app
```

Required:

```bash
GITHUB_APP_ID=...
GITHUB_PRIVATE_KEY=...
GITHUB_WEBHOOK_SECRET=...
```

`/webhook` uses GitHub signature verification. Do not put Dashboard login in front of the webhook route.

## MCP Deployment

MCP is a local stdio server:

```bash
mgreview-mcp
```

It does not start HTTP. It is mainly intended for local tools such as Claude Desktop or Cursor. Remote/hosted MCP is a future or advanced deployment path.

## Environment Variables

Common groups:

- Dashboard: `MGREVIEW_DASHBOARD_HOST`, `MGREVIEW_DASHBOARD_PORT`
- Storage: `MGREVIEW_DB_PATH`
- Auth: `MGREVIEW_AUTH_ENABLED`, `MGREVIEW_ADMIN_PASSWORD`, `MGREVIEW_SESSION_SECRET`, `MGREVIEW_API_KEYS`
- GitHub App: `GITHUB_APP_ID`, `GITHUB_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`
- LLM: `MGREVIEW_LLM_PROVIDER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`
- Network policy: `MGREVIEW_NETWORK_ENABLED`, `MGREVIEW_ALLOW_LLM`, `MGREVIEW_CODE_SHARING_MODE`

Never commit `.env`.

## Volumes And SQLite Persistence

Default local DB:

```text
.magicreview/magicreview.db
```

Docker DB:

```text
/data/magicreview.db
```

Back up the SQLite database before upgrades.

## Reverse Proxy Overview

Example Nginx proxy:

```nginx
server {
    listen 80;
    server_name review.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## HTTPS Requirement

Use one of:

- Caddy automatic HTTPS
- Nginx + certbot
- Cloudflare Tunnel
- Tailscale or WireGuard private network

Set `MGREVIEW_COOKIE_SECURE=true` when serving the Dashboard over HTTPS.

## Production Checklist

- Auth enabled
- Strong admin password
- Random session secret
- Bearer API token configured
- HTTPS or private network
- `.env` not committed
- SQLite backup plan
- LLM provider disabled unless approved
- NetworkPolicy reviewed
- GitHub webhook secret configured

## Troubleshooting

- Dashboard health: `GET /health`
- GitHub App health: `GET /health` on port `8000`
- Docker config: `docker compose config`
- Docker build timeout: pre-pull `python:3.12-slim` or configure a registry mirror
- Missing GitHub credentials: Dashboard can still start; webhook processing needs credentials




