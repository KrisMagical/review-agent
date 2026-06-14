# Privacy

MagicReview is local-first and offline by default.

## Local-First Privacy Model

By default, MagicReview:

- reviews files, diffs, and projects locally
- does not upload source code
- does not call real LLM providers
- does not call remote MCP servers
- does not modify source files
- does not execute reviewed project code

## What Runs Offline

Offline by default:

- `mgreview file`
- `mgreview diff`
- `mgreview project`
- enterprise rules
- FastAPI rules
- multi-agent static checks
- MCP stdio server
- Dashboard browsing of local SQLite data
- mock LLM provider

## What Can Trigger Network Access

Network access can happen only when configured:

- real LLM provider review
- GitHub App webhook PR review
- Hosted Review GitHub PR URL review
- GitHub `full_project` PR file fetch
- future remote/hosted MCP deployment

## LLM Provider Data Sharing

LLM review sends bounded prompts to the configured provider only when explicitly enabled.

CLI example:

```bash
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

`--llm` alone is not network consent.

## code_sharing_mode

- `none`: send no code or summaries
- `summary_only`: send project structure, file summaries, and issue summaries
- `snippets`: may send selected source snippets
- `full_context`: may send broader source context

Use `summary_only` for sensitive code unless broader sharing is approved.

## GitHub App Data Access

GitHub App modes:

- `diff_only`: fetches PR diff only
- `full_project`: fetches Python/config/limited metadata files for the PR head commit through Trees/Blob APIs

`full_project` is not a full repository mirror. It skips `.env`, private keys, virtual environments, `node_modules`, and build/cache folders. Truncated Git trees return a safe error.

## MCP Local Vs Remote

Current MCP is stdio and local by default:

```bash
mgreview-mcp
```

It does not start HTTP and does not call remote services unless optional LLM/network policy settings are explicitly provided.

## Dashboard Storage

Dashboard stores:

- projects
- review runs
- normalized issue records
- summary counts
- sanitized metadata
- network audit records
- optional model provider settings

SQLite defaults to:

```text
.magicreview/magicreview.db
```

## Network Audit

Audit records include:

- timestamp
- source
- provider
- operation
- code sharing mode
- status
- sanitized metadata

They do not include full prompts, source code, API keys, private keys, or tokens.

## What Is Never Stored

MagicReview should not store:

- GitHub installation tokens
- GitHub private keys
- full LLM prompts
- full uploaded diffs in Hosted Review metadata
- full source files from GitHub full_project mode
- complete API keys in UI/API output

Model API keys stored in SQLite are masked in UI/API output but are not encrypted at rest in this phase. Prefer environment variables or a secret manager in production.

## What Is Never Sent By Default

By default, MagicReview sends nothing to:

- OpenAI
- Anthropic
- Azure OpenAI
- external gateways
- GitHub APIs
- remote MCP servers

## Recommended Settings For Sensitive Code

- Keep `MGREVIEW_LLM_PROVIDER=none`.
- Keep `MGREVIEW_NETWORK_ENABLED=false`.
- Use local CLI or Dashboard only.
- If LLM is approved, use `summary_only`.
- Prefer local Ollama or an enterprise gateway for regulated code.
- Enable Dashboard auth and HTTPS.
- Back up SQLite securely.

## Current Limits

- No encrypted-at-rest model key storage yet.
- No RBAC or SSO.
- Hosted reviews run synchronously.
- GitHub `full_project` is limited to selected file types and repository size limits.



