# Hosted Review Web UI

Phase 11.5 adds a Dashboard Review Center so users can trigger reviews without the CLI.

## Hosted Review Overview

Open:

```text
/review
```

The Review Center links to:

- `/review/diff`
- `/review/project`
- `/review/github-pr`

When Dashboard auth is enabled, these pages require login.

## /review

The landing page explains the three review paths and links to their forms.

## /review/diff

Use this page to:

- paste unified diff text
- upload a `.diff` or `.patch` file
- optionally save the result to Dashboard
- choose LLM/network options

Security behavior:

- empty diffs are rejected
- uploads are read as UTF-8
- upload size is limited by `MGREVIEW_MAX_UPLOAD_BYTES`
- uploaded files are not saved as source artifacts
- zip/tar extraction is not supported
- uploaded contents are not executed

```bash
MGREVIEW_MAX_UPLOAD_BYTES=5242880
```

## /review/project

Use this page to review a server-local project path.

Allowed roots:

```bash
MGREVIEW_ALLOWED_REVIEW_ROOTS=/workspace,/repos
```

Rules:

- `project_path` must resolve under an allowed root
- `config_path` must also be inside an allowed root or the project path
- path traversal is rejected
- reviewed code is not executed or imported

Docker Compose mounts the repository read-only at `/workspace`.

## /review/github-pr

Use GitHub PR URLs:

```text
https://github.com/owner/repo/pull/123
```

This path requires `GITHUB_TOKEN` for Web UI GitHub API access and explicit network authorization in the form.

## GitHub PR Review Modes

The form supports:

- `diff_only`: fetches and reviews the PR diff
- `full_project`: fetches Python/config/limited metadata files for the PR head commit, builds a temporary directory, and runs project review

`full_project` supports enterprise rules, agents, architecture checks, and project-level findings. It is more expensive than `diff_only` and still does not enable LLM unless you explicitly enable LLM and network policy options.

## diff_only Vs full_project

`diff_only`:

- lowest cost
- best for quick PR comments
- mostly changed-line findings

`full_project`:

- fetches selected repository files through GitHub Trees/Blob APIs
- reads repository MagicReview config files
- calls `ReviewService.review_project`
- emits project-level findings in summary when not mappable to changed lines
- skips secrets and enforces size limits

## Save Result

When `save_result=true`, MagicReview stores:

- normalized issues
- summary counts
- sanitized metadata
- source as `dashboard`
- target type as `diff`, `project`, or `github_pr`

It does not store:

- full uploaded diff
- GitHub token
- API keys
- LLM prompt

Saved runs are visible at `/reviews/{id}`.

## NetworkPolicy

Hosted review forms expose:

- `enable_llm`
- `enable_agents`
- `enable_enterprise_rules`
- `llm_provider`
- `allow_network`
- `allow_llm`
- `code_sharing_mode`

Defaults are offline.

Real LLM providers require:

- `enable_llm=true`
- `allow_network=true`
- `allow_llm=true`
- `code_sharing_mode != none`

GitHub PR fetching also requires network authorization.

## Dashboard API

- `GET /api/review/options`
- `POST /api/review/diff`
- `POST /api/review/project`
- `POST /api/review/github-pr`

When auth is enabled, use session auth or:

```http
Authorization: Bearer <token>
```

## Security Limits

- Reviews run synchronously; there is no queue.
- No automatic fixes, commits, or pushes.
- No RBAC or multi-user workspace.
- GitHub PR review requires explicit GitHub token/network permission.
- LLM providers remain disabled by default.



