# Model Providers

Phase 11.4 adds Dashboard model provider settings for optional LLM architecture review and AI-assisted code review.

## Provider Overview

Default provider:

```bash
REVIEWAGENT_LLM_PROVIDER=none
```

ReviewAgent does not call real LLM providers by default. Real providers require:

- API key or endpoint configuration
- explicit NetworkPolicy authorization
- `allow_network=true`
- `allow_llm=true`
- `code_sharing_mode != none`

## Dashboard /settings/models

Open:

```text
/settings/models
```

The page lets authenticated Dashboard users:

- select a provider
- configure model/base URL
- store or clear a local API key
- see API key source and masked key
- choose `code_sharing_mode`
- enable/disable network and LLM access
- test provider connection

The page never displays the full API key.

## Environment Variable Configuration

Environment variables take priority over stored settings:

```bash
REVIEWAGENT_LLM_PROVIDER=none
REVIEWAGENT_LLM_MODEL=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=
REVIEWAGENT_OPENAI_COMPATIBLE_BASE_URL=
REVIEWAGENT_OPENAI_COMPATIBLE_API_KEY=
REVIEWAGENT_OLLAMA_BASE_URL=http://localhost:11434
REVIEWAGENT_ENTERPRISE_LLM_BASE_URL=
REVIEWAGENT_ENTERPRISE_LLM_API_KEY=
```

## OpenAI

```bash
REVIEWAGENT_LLM_PROVIDER=openai
REVIEWAGENT_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

CLI usage:

```bash
review project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

## Anthropic

```bash
REVIEWAGENT_LLM_PROVIDER=anthropic
REVIEWAGENT_LLM_MODEL=claude-3-5-sonnet-latest
ANTHROPIC_API_KEY=...
```

```bash
review project . --llm --llm-provider anthropic --allow-network --allow-llm --code-sharing summary-only
```

## Azure OpenAI

```bash
REVIEWAGENT_LLM_PROVIDER=azure_openai
AZURE_OPENAI_ENDPOINT=https://example.openai.azure.com
AZURE_OPENAI_DEPLOYMENT=my-deployment
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_OPENAI_API_KEY=...
```

## OpenAI-Compatible Endpoint

```bash
REVIEWAGENT_LLM_PROVIDER=openai_compatible
REVIEWAGENT_OPENAI_COMPATIBLE_BASE_URL=https://gateway.example.com/v1
REVIEWAGENT_OPENAI_COMPATIBLE_API_KEY=...
REVIEWAGENT_LLM_MODEL=your-model
```

Use this for private gateways and providers that expose an OpenAI-style API.

## Ollama / Local Model

```bash
REVIEWAGENT_LLM_PROVIDER=ollama
REVIEWAGENT_LLM_MODEL=llama3.1
REVIEWAGENT_OLLAMA_BASE_URL=http://localhost:11434
```

Docker host Ollama is often:

```bash
REVIEWAGENT_OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Linux Docker may need host gateway configuration. If Ollama points to a remote server, treat it as networked.

## Enterprise Gateway

```bash
REVIEWAGENT_LLM_PROVIDER=enterprise_gateway
REVIEWAGENT_ENTERPRISE_LLM_BASE_URL=https://llm-gateway.example.com/v1
REVIEWAGENT_ENTERPRISE_LLM_API_KEY=...
REVIEWAGENT_LLM_MODEL=approved-model
```

Use this when your organization routes AI traffic through an internal gateway.

## code_sharing_mode

- `none`: do not send code or summaries
- `summary_only`: send project structure, file summaries, and issue summaries
- `snippets`: may send relevant source snippets
- `full_context`: may send larger source context

`summary_only` is recommended for most external providers. `snippets` and `full_context` should be used only after explicit approval.

## NetworkPolicy

Real network providers are blocked unless the policy allows them:

```json
{
  "enabled": true,
  "allow_llm": true,
  "code_sharing_mode": "summary_only",
  "allowed_providers": ["openai"]
}
```

Mock provider works offline. `none` disables LLM.

## Test Connection

The Dashboard provider test sends only:

```text
Reply with OK.
```

It does not send project code. Real provider tests are blocked unless network and LLM permission are enabled.

## API Key Storage And Masking

- Environment variables take priority.
- API responses return masked keys such as `sk-****abcd`.
- Full API keys are not rendered in HTML.
- Keys are not written to logs.
- Keys are not stored in network audit metadata.
- Stored SQLite keys are masked in UI/API output but are not encrypted at rest in this phase.

Production deployments should prefer environment variables, Docker secrets, or a secret manager.

## Docker Model Config

Add model variables to `.env`, then:

```bash
docker compose up dashboard
```

For real providers, also configure:

```bash
REVIEWAGENT_NETWORK_ENABLED=true
REVIEWAGENT_ALLOW_LLM=true
REVIEWAGENT_CODE_SHARING_MODE=summary_only
```

## Security Notes

- Default provider is `none`.
- Dashboard settings do not make CLI `review project .` call LLM automatically.
- CLI still requires `--llm` and network flags for real providers.
- Do not put API keys in Git.
- Avoid `full_context` for sensitive projects.

## Current Limits

- No per-user provider settings.
- No RBAC or SSO.
- Stored keys are not encrypted at rest.
- Provider settings are local/self-hosted, not a SaaS control plane.
