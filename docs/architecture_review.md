# LLM Architecture Review

Phase 5 adds an optional LLM architecture review stage on top of the static
Phase 1-4 analyzers.

It looks for architecture and maintainability risks such as SRP violations,
heavy route handlers, service responsibility drift, module boundary issues,
layering problems, high coupling, and refactor opportunities.

## Why it is disabled by default

Architecture review may send a bounded project summary to the configured LLM
provider. It is therefore disabled unless explicitly requested.

## Enable from CLI

```bash
python -m magicreview.cli.main project examples/architecture_bad_project --llm
```

Use the mock provider for local dry runs:

```bash
python -m magicreview.cli.main project examples/architecture_bad_project --llm --llm-provider mock
```

## MCP

`review_project` accepts:

```json
{
  "path": "examples/architecture_bad_project",
  "enable_llm": true,
  "llm_provider": "mock"
}
```

## Providers

Environment variables:

```bash
MGREVIEW_LLM_PROVIDER=none|mock|openai
MGREVIEW_LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=...
```

Default provider is `none`, which never calls an external model.

## Output

Architecture review returns the same Issue JSON shape:

```json
{
  "issues": [
    {
      "severity": "medium",
      "type": "MaintainabilityRisk",
      "file": "app/services/user_service.py",
      "line": 1,
      "message": "Service responsibilities drift across domains.",
      "suggestion": "Split unrelated orchestration into focused services."
    }
  ]
}
```

## Limits

- The context builder reads source text but does not import or execute project modules.
- It sends summaries, not full large-project source.
- Hidden directories, virtual environments, `.git`, caches, and dependency folders are skipped by the project scanner.
- Invalid LLM output is converted into `ArchitectureReviewError`.
- Enterprise rule configuration belongs to Phase 5.5.
- Multi-agent collaboration belongs to Phase 6.
## Network Policy

MagicReview remains offline by default. `--llm` enables the architecture review stage, but real network providers such as OpenAI or Anthropic also require explicit network authorization:

```bash
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
```

The mock provider does not require network authorization.
