# Dashboard

The Dashboard is MagicReview's local governance UI for review history, issue trends, model settings, hosted review, and connected-service audit.

## Dashboard Overview

The Dashboard stores optional review results in SQLite and shows:

- projects
- review runs
- issue details
- severity summaries
- issue trends
- bug trends
- technical debt trends
- architecture risk trends
- team statistics
- network audit records

It does not replace CLI, MCP, or GitHub App workflows.

## Start Dashboard

```bash
mgreview dashboard init-db
mgreview dashboard serve --host 127.0.0.1 --port 8080
```

Other entry points:

```bash
mgreview-dashboard
python -m magicreview.dashboard.app
```

Docker:

```bash
docker compose up dashboard
```

## Auth

Auth is disabled by default for local development. Enable before server/public access:

```bash
MGREVIEW_AUTH_ENABLED=true
MGREVIEW_ADMIN_USERNAME=admin
MGREVIEW_ADMIN_PASSWORD=...
MGREVIEW_SESSION_SECRET=...
MGREVIEW_API_KEYS=...
```

When enabled:

- pages redirect to `/login`
- `/logout` clears the session
- APIs accept session or Bearer token
- optional Basic Auth is available
- `/health` remains public

## Projects

Projects are created when saved review results include project metadata. The project pages show review history and high-level risk information.

## Review Runs

Review runs store:

- source: `cli`, `github`, `dashboard`, `mcp`, or `api`
- target type: `file`, `diff`, `project`, or `pull_request`
- target ref
- severity counts
- sanitized metadata
- issue records

## Issue Trends

Trend endpoints group stored issues by day and severity. The Dashboard also derives bug, technical debt, and architecture-risk trends from issue type/category.

## Network Audit

Routes:

- `/audit/network`
- `GET /api/audit/network`
- `GET /api/audit/network/{id}`

Audit data does not include API keys, tokens, full prompts, or full source code.

## Model Settings

Open:

```text
/settings/models
```

Configure provider, model, masked API key, NetworkPolicy, and code sharing mode. Real providers remain blocked unless explicitly authorized.

## Hosted Review Web UI

Open:

```text
/review
```

Pages:

- `/review/diff`
- `/review/project`
- `/review/github-pr`

Hosted project review is restricted by `MGREVIEW_ALLOWED_REVIEW_ROOTS`.

## GitHub PR full_project Metadata

When GitHub `full_project` mode is used and results are saved, metadata may include:

- review mode
- owner/repo
- PR number
- base/head sha
- fetched/skipped file counts
- enable agents/LLM flags
- code sharing mode

It does not store token, source files, full diff, private keys, or full prompt.

## SQLite Storage

Default:

```text
.magicreview/magicreview.db
```

Docker:

```text
/data/magicreview.db
```

Override:

```bash
MGREVIEW_DB_PATH=/path/to/magicreview.db
```

## Docker Deployment

```bash
docker compose up dashboard
```

Open:

```text
http://127.0.0.1:8080
```

Compose mounts `.magicreview` for database persistence and `/workspace` for hosted project review.

## API Routes

- `GET /health`
- `GET /api/projects`
- `GET /api/projects/{project_id}`
- `GET /api/projects/{project_id}/reviews`
- `GET /api/reviews`
- `GET /api/reviews/{review_run_id}`
- `GET /api/reviews/{review_run_id}/issues`
- `GET /api/stats/overview`
- `GET /api/stats/trends/issues`
- `GET /api/stats/trends/bugs`
- `GET /api/stats/trends/technical-debt`
- `GET /api/stats/trends/architecture-risk`
- `GET /api/stats/team`
- `GET /api/audit/network`
- `GET /api/audit/network/{id}`
- `GET /api/settings/models`
- `POST /api/settings/models`
- `POST /api/settings/models/test`
- `DELETE /api/settings/models/api-key`
- `GET /api/review/options`
- `POST /api/review/diff`
- `POST /api/review/project`
- `POST /api/review/github-pr`

## Pages

- `/` or `/dashboard`
- `/login`
- `/logout`
- `/projects`
- `/projects/{id}`
- `/reviews/{id}`
- `/audit/network`
- `/settings/models`
- `/review`
- `/review/diff`
- `/review/project`
- `/review/github-pr`

## Security Notes

- Default host is local development oriented.
- Enable auth and HTTPS before server/public access.
- Do not expose unauthenticated Dashboard publicly.
- Dashboard does not execute reviewed code.
- API key output is masked.
- Uploaded diffs are not stored in metadata.

## Current Limits

- No RBAC or multi-user workspace.
- No background queue; hosted reviews run synchronously.
- No advanced frontend framework.
- No SaaS tenant isolation.




