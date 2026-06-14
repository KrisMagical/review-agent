# Architecture bad project

This sample project contains architecture smells for Phase 5 LLM architecture review:

- heavy route handlers
- service responsibility drift
- repository access from routes
- unclear module boundaries
- high coupling around service orchestration

Run static review:

```bash
python -m magicreview.cli.main project examples/architecture_bad_project
```

Run architecture review with the mock provider:

```bash
python -m magicreview.cli.main project examples/architecture_bad_project --llm --llm-provider mock
```

Real LLM providers must be enabled explicitly with environment variables.
