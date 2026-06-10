# Self Hosting

ReviewAgent can be self-hosted on a single server, internal VM, private network, or Docker host.

## Self-Hosting Overview

Recommended model:

- Dashboard runs privately on port `8080`
- GitHub App webhook server runs on port `8000`
- SQLite is stored in `.reviewagent` or `/data`
- Auth is enabled for Dashboard
- GitHub webhook signature is enabled for GitHub App
- LLM providers are disabled unless explicitly approved

## Single-Server Deployment

```bash
git clone https://github.com/KrisMagical/review-agent.git
cd review-agent
pip install -e ".[all]"
review dashboard init-db
review dashboard serve --host 127.0.0.1 --port 8080
```

Use a reverse proxy for HTTPS and public/private access.

## Docker Compose Deployment

```bash
cp .env.example .env
docker compose up dashboard
docker compose up github-app
```

Use `.env` for secrets and do not commit it.

## Private Network Deployment

For internal teams, prefer:

- VPN
- Tailscale
- WireGuard
- private subnet
- SSH tunnel

Dashboard does not need to be public for GitHub App review to work.

## Tailscale Deployment

Run Dashboard on the server:

```bash
docker compose up dashboard
```

Expose only through the Tailscale IP or MagicDNS hostname. Keep Dashboard auth enabled for defense in depth.

## Cloudflare Tunnel Deployment

Cloudflare Tunnel can expose Dashboard or GitHub App without opening inbound ports.

Use Dashboard auth for Dashboard. Keep GitHub `/webhook` signature verification enabled.

## Nginx Reverse Proxy

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

Use certbot or another certificate manager for HTTPS.

## Caddy Reverse Proxy

```caddyfile
review.example.com {
    reverse_proxy 127.0.0.1:8080
}
```

Caddy can manage HTTPS automatically.

## HTTPS

Set:

```bash
REVIEWAGENT_COOKIE_SECURE=true
```

only when the Dashboard is served over HTTPS.

## Backup SQLite Database

Back up:

```text
.reviewagent/reviewagent.db
```

or Docker path:

```text
/data/reviewagent.db
```

Stop the service or use SQLite-safe backup tooling before copying a busy DB.

## Updating ReviewAgent

From source:

```bash
git pull
pip install -e ".[all]"
pytest --basetemp=.pytest_tmp
```

Docker:

```bash
docker build -t reviewagent .
docker compose up -d
```

Back up SQLite before upgrades.

## Security Checklist

- `REVIEWAGENT_AUTH_ENABLED=true`
- strong admin password
- random `REVIEWAGENT_SESSION_SECRET`
- Bearer API token configured
- HTTPS or private network
- `.env` outside Git
- GitHub webhook secret configured
- LLM providers disabled unless approved
- `code_sharing_mode=summary_only` for external providers
- Dashboard not exposed unauthenticated

## Current Limits

- No RBAC.
- No SaaS tenant isolation.
- No OAuth/SSO.
- No background queue.
- No automatic code modification.
- Dashboard is appropriate for personal, team-internal, and controlled-server use.
