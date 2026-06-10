# GitHub App

ReviewAgent can run as a GitHub App and review pull requests through webhooks.

## GitHub App Overview

Flow:

```text
Pull Request -> Webhook -> ReviewAgent GitHub App -> ReviewService -> PR comments / Dashboard
```

ReviewAgent supports:

- PR summary comment
- inline comments for changed lines
- optional check run
- optional Dashboard persistence
- `diff_only` and `full_project` review modes

It does not automatically fix, commit, or push code.

## Required Permissions

Repository permissions:

- Contents: Read
- Pull requests: Read & Write
- Issues: Read & Write
- Checks: Read & Write, optional
- Metadata: Read

Webhook events:

- Pull request

Handled actions:

- opened
- synchronize
- reopened
- ready_for_review

Other actions are ignored safely.

## Webhook Setup

Webhook URL:

```text
https://your-domain.example.com/webhook
```

Local development can use ngrok, Cloudflare Tunnel, or another tunnel.

The same webhook secret must be configured in GitHub and in `GITHUB_WEBHOOK_SECRET`.

## Environment Variables

```bash
GITHUB_APP_ID=12345
GITHUB_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----..."
GITHUB_WEBHOOK_SECRET="your-webhook-secret"
GITHUB_APP_NAME=ReviewAgent

REVIEWAGENT_GITHUB_ENABLE_INLINE_COMMENTS=true
REVIEWAGENT_GITHUB_ENABLE_SUMMARY_COMMENT=true
REVIEWAGENT_GITHUB_ENABLE_AGENTS=false
REVIEWAGENT_GITHUB_ENABLE_LLM=false
REVIEWAGENT_GITHUB_CONFIG_PATH=
REVIEWAGENT_GITHUB_MAX_INLINE_COMMENTS=30
REVIEWAGENT_GITHUB_FAIL_ON=high
REVIEWAGENT_GITHUB_SAVE_RESULTS=true
REVIEWAGENT_GITHUB_REVIEW_MODE=diff_only

REVIEWAGENT_GITHUB_MAX_PROJECT_FILES=2000
REVIEWAGENT_GITHUB_MAX_FILE_BYTES=2097152
REVIEWAGENT_GITHUB_MAX_PROJECT_BYTES=52428800
REVIEWAGENT_GITHUB_FETCH_TIMEOUT_SECONDS=30
REVIEWAGENT_GITHUB_ALLOW_NETWORK=false
REVIEWAGENT_GITHUB_ALLOW_LLM=false
REVIEWAGENT_GITHUB_CODE_SHARING_MODE=none

REVIEWAGENT_GITHUB_HOST=0.0.0.0
REVIEWAGENT_GITHUB_PORT=8000
```

Do not commit private keys or webhook secrets.

## Start Server

```bash
reviewagent-github-app
```

Alternative:

```bash
python -m reviewagent.integrations.github.app
```

Routes:

- `GET /health`
- `POST /webhook`

`/health` does not expose secrets.

## diff_only Mode

Default:

```bash
REVIEWAGENT_GITHUB_REVIEW_MODE=diff_only
```

Behavior:

- fetch PR diff
- run `ReviewService.review_diff`
- map changed-line issues to inline comments
- include remaining findings in summary

This is fast and has limited project-level context.

## full_project Mode

Optional:

```bash
REVIEWAGENT_GITHUB_REVIEW_MODE=full_project
```

Behavior:

- fetch PR head commit file tree with GitHub Trees API
- fetch selected blobs with GitHub Blob API
- write a temporary project directory
- run `ReviewService.review_project`
- clean the temporary directory

Fetched file types:

- `.py`
- ReviewAgent config files
- `pyproject.toml`
- `README.md`

Skipped:

- `.env`
- private keys
- `.git`
- virtual environments
- `node_modules`
- build/cache folders

## full_project Limitations

`full_project` is not a full repository mirror. It fetches Python/config/limited metadata files only.

Limits:

- `REVIEWAGENT_GITHUB_MAX_PROJECT_FILES`
- `REVIEWAGENT_GITHUB_MAX_FILE_BYTES`
- `REVIEWAGENT_GITHUB_MAX_PROJECT_BYTES`
- `REVIEWAGENT_GITHUB_FETCH_TIMEOUT_SECONDS`

If the Git tree is truncated, ReviewAgent returns a safe `GitHubProjectFetchError` instead of continuing with incomplete context.

## GitHub App Installation Token

Webhook mode uses:

1. `GITHUB_APP_ID`
2. `GITHUB_PRIVATE_KEY`
3. installation id from webhook payload
4. installation access token

Tokens are not stored in Dashboard metadata and are not logged.

## GITHUB_TOKEN Use In Web UI

The Hosted Review Web UI `/review/github-pr` can use:

```bash
GITHUB_TOKEN=...
```

This is separate from GitHub App installation-token flow and is intended for user-triggered Dashboard review.

## Summary Comments

ReviewAgent upserts one summary comment with marker:

```html
<!-- reviewagent-summary -->
```

The summary includes severity counts, top issues, and review mode.

## Inline Comments

Inline comments are created only for issues that map to changed PR lines.

Marker:

```html
<!-- reviewagent-inline:IssueType:path.py:20 -->
```

This avoids repeated comments across pushes.

## Checks

When configured, ReviewAgent can create a `ReviewAgent` check run. `REVIEWAGENT_GITHUB_FAIL_ON=high` marks the check as failed when high or critical issues exist.

## Dashboard Persistence

Enable:

```bash
REVIEWAGENT_GITHUB_SAVE_RESULTS=true
```

Stored metadata is sanitized and may include:

- review mode
- owner/repo
- PR number
- base/head sha
- action
- file counts
- enable agents/LLM flags

Not stored:

- tokens
- private keys
- full diff
- full source files
- full LLM prompt

## Security Notes

- Webhook signatures use `X-Hub-Signature-256`.
- PR code is not executed or imported.
- LLM is disabled by default.
- Dashboard auth is separate from GitHub webhook auth.
- Do not put Dashboard login in front of `/webhook`.
- Inline comments are capped by `REVIEWAGENT_GITHUB_MAX_INLINE_COMMENTS`.

## Troubleshooting

- 401 webhook: check `GITHUB_WEBHOOK_SECRET`.
- No comments: check repository permissions.
- `GitHubProjectFetchError`: check repository size, tree truncation, and token permissions.
- Missing Dashboard records: set `REVIEWAGENT_GITHUB_SAVE_RESULTS=true`.
- LLM not running: confirm `REVIEWAGENT_GITHUB_ENABLE_LLM=true` and network policy.
