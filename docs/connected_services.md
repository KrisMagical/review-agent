# Connected Services

MagicReview is local-first and offline by default. Connected Services are opt-in integrations that may call external systems such as LLM providers or GitHub APIs.

## Connected Services Overview

Potential networked operations:

- real LLM architecture review
- Dashboard provider connection tests
- GitHub App PR review
- Hosted Review GitHub PR URL review
- GitHub `full_project` file fetch
- future remote MCP deployments

Mock LLM, local CLI review, enterprise rules, and Dashboard browsing of stored SQLite data remain offline.

## NetworkPolicy

NetworkPolicy gates connected operations:

```json
{
  "enabled": false,
  "allow_llm": false,
  "allow_github_api": false,
  "allow_remote_mcp": false,
  "code_sharing_mode": "none",
  "allowed_providers": [],
  "require_explicit_consent": true,
  "audit_enabled": true
}
```

## LLM Provider Rules

Real LLM providers require:

- `enabled=true`
- `allow_llm=true`
- approved provider
- `code_sharing_mode` not `none`

CLI:

```bash
mgreview project . --llm --llm-provider mock
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

`--llm` alone is not network consent.

## GitHub Networking

GitHub App and Hosted Review GitHub PR mode call GitHub APIs only when configured.

GitHub App review mode:

```bash
MGREVIEW_GITHUB_REVIEW_MODE=diff_only
MGREVIEW_GITHUB_REVIEW_MODE=full_project
```

- `diff_only`: fetches the PR diff and reviews changed lines.
- `full_project`: fetches Python/config/limited metadata files for the PR head commit through Trees/Blob APIs, builds a temporary directory, and runs project review.

`full_project` is not a full repository mirror and skips secret-like files.

## MCP Networking

Current MCP is local stdio:

```bash
mgreview-mcp
```

`review_project` can accept a `network_policy` for optional LLM review. Without it, MCP remains offline.

## Dashboard Network Audit

Audit routes:

- `GET /api/audit/network`
- `GET /api/audit/network/{id}`
- `/audit/network`

Audit records include provider, operation, source, sharing mode, status, and sanitized metadata.

They do not include:

- API keys
- tokens
- private keys
- full prompts
- full source code

## allow_network / allow_llm

Use both for real LLM providers:

- `allow_network`: permits network operations under the selected policy
- `allow_llm`: permits LLM provider calls

For GitHub PR URL review, GitHub fetches require network permission. LLM remains separately controlled.

## code_sharing_mode

- `none`: no code or summaries
- `summary_only`: bounded project and issue summaries
- `snippets`: selected snippets may be sent
- `full_context`: broader source context may be sent

Use `summary_only` for external providers unless a broader mode is formally approved.

## Examples

MCP:

```json
{
  "path": ".",
  "enable_llm": true,
  "llm_provider": "openai",
  "network_policy": {
    "enabled": true,
    "allow_llm": true,
    "code_sharing_mode": "summary_only",
    "allowed_providers": ["openai"]
  }
}
```

GitHub full project:

```bash
MGREVIEW_GITHUB_REVIEW_MODE=full_project
MGREVIEW_GITHUB_ENABLE_AGENTS=true
MGREVIEW_GITHUB_ENABLE_LLM=false
```

## Current Limits

- No remote MCP hosting workflow is provided by default.
- No SaaS control plane.
- LLM usage accounting is limited to local audit records.
- `full_context` depends on provider limits and should be avoided for sensitive repositories.



