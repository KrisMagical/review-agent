# Dashboard Authentication

Phase 11.3 adds private web access for the Dashboard. Authentication is disabled by default for local development and should be enabled for any server, tunnel, or public-domain deployment.

## Auth Overview

When enabled, Dashboard pages require a session login and Dashboard API routes require either:

- an authenticated session cookie
- `Authorization: Bearer <api-key>`
- optional HTTP Basic Auth

`/health` remains public for health checks.

## Environment Variables

```bash
REVIEWAGENT_AUTH_ENABLED=true
REVIEWAGENT_ADMIN_USERNAME=admin
REVIEWAGENT_ADMIN_PASSWORD=use-a-strong-password
REVIEWAGENT_SESSION_SECRET=use-a-random-secret
REVIEWAGENT_API_KEYS=token-one,token-two
REVIEWAGENT_COOKIE_SECURE=false
REVIEWAGENT_BASIC_AUTH_ENABLED=false
```

Generate a secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## REVIEWAGENT_AUTH_ENABLED

Default:

```bash
REVIEWAGENT_AUTH_ENABLED=false
```

Local development can keep auth disabled. Server deployments should set it to `true`.

## Admin Username And Password

The initial implementation reads the admin password from environment variables.

Security notes:

- The password is not returned to the UI.
- The password is not logged.
- Comparison uses constant-time checks.
- Production should inject it through environment variables, Docker secrets, or a secret manager.
- Future releases can add hashed passwords, RBAC, SSO, or multi-user management.

## Session Cookie

The Dashboard uses a signed session cookie.

Important settings:

- `REVIEWAGENT_SESSION_SECRET`: required for stable sessions
- `REVIEWAGENT_COOKIE_SECURE`: set `true` when served over HTTPS

Cookie behavior:

- HTTP-only
- SameSite Lax
- Session invalidates if the secret changes

## API Bearer Token

Configure one or more keys:

```bash
REVIEWAGENT_API_KEYS=dev-token,automation-token
```

Call API routes:

```http
Authorization: Bearer dev-token
```

Invalid or missing tokens return:

```json
{"detail": "Authentication required"}
```

## Basic Auth

Optional:

```bash
REVIEWAGENT_BASIC_AUTH_ENABLED=true
```

Basic Auth uses the same admin username/password. It is useful for simple deployments, but session login and Bearer tokens are preferred.

## Local Mode Vs Server Mode

Local:

```bash
REVIEWAGENT_AUTH_ENABLED=false
review dashboard serve --host 127.0.0.1 --port 8080
```

Server:

```bash
REVIEWAGENT_AUTH_ENABLED=true
REVIEWAGENT_COOKIE_SECURE=true
review dashboard serve --host 0.0.0.0 --port 8080
```

Use HTTPS before setting secure cookies.

## Docker Auth Setup

```bash
cp .env.example .env
```

Edit `.env`:

```bash
REVIEWAGENT_AUTH_ENABLED=true
REVIEWAGENT_ADMIN_USERNAME=admin
REVIEWAGENT_ADMIN_PASSWORD=...
REVIEWAGENT_SESSION_SECRET=...
REVIEWAGENT_API_KEYS=...
```

Then:

```bash
docker compose up dashboard
```

## Reverse Proxy Auth Notes

ReviewAgent auth protects the Dashboard. You can still place it behind:

- Nginx
- Caddy
- Cloudflare Tunnel
- Tailscale
- WireGuard

Do not rely on an unauthenticated public reverse proxy.

## GitHub Webhook Signature Is Separate

Dashboard auth and GitHub webhook auth are different:

- Dashboard pages/API use session, Bearer token, and optional Basic Auth.
- GitHub `/webhook` uses `X-Hub-Signature-256` and `GITHUB_WEBHOOK_SECRET`.
- Do not require Dashboard login on `/webhook`; GitHub cannot complete interactive login.
- GitHub App `/health` may remain public.

## Current Limits

- No RBAC.
- No multiple user accounts.
- No OAuth, SSO, SAML, or SCIM.
- Password hashing is planned for a future hardening phase.
- Dashboard is best suited for personal, team-internal, or private-network deployments.
