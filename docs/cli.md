# CLI

The `review` CLI is the quickest way to use ReviewAgent locally. It calls the same ReviewService used by MCP, GitHub App, Dashboard, enterprise rules, LLM review, and multi-agent review.

## Install

```bash
pip install -e ".[all]"
review --help
review --version
```

Run without console scripts:

```bash
python -m reviewagent.cli.main --help
```

## Review File

```bash
review file examples/bad_code.py
review file examples/bad_code.py --format terminal
review file examples/bad_code.py --format json --fail-on high
review file examples/bad_code.py --config reviewagent.yml
review file examples/bad_code.py --save
```

`--config` enables explicit enterprise YAML/JSON rules for the file review path when supported by the rule.

## Review Diff

`review diff` reads unified diff text from stdin by default:

```bash
git diff | review diff --format terminal
cat examples/sample.diff | review diff --format json
```

Read a patch file:

```bash
review diff --file examples/sample.diff --format markdown --output diff-review.md
review diff --file examples/sample.diff --save
```

## Review Project

```bash
review project .
review project . --format terminal
review project examples/phase2_bad_project --format markdown --output review.md
review project examples/enterprise_policy_project --config examples/enterprise_policy_project/reviewagent.yml
review project examples/multi_agent_project --agents
review project examples/multi_agent_project --agents quality,security
```

## Output Formats

Supported `--format` values:

- `json`
- `terminal`
- `markdown`
- `html`

JSON is the default for automation and includes `issues` plus `summary`.

Write a report file:

```bash
review project . --format html --output review.html
review diff --file changes.patch --format markdown --output review.md
```

## Filtering And Limits

```bash
review project . --severity high
review project . --max-issues 50
```

`--severity high` shows only `high` and `critical` issues.

## Save Results

Saving is opt-in:

```bash
review project . --save
review file app/main.py --save
review diff --file changes.patch --save
```

Saved results go to SQLite at `REVIEWAGENT_DB_PATH` or `.reviewagent/reviewagent.db`.

## Enterprise Rules

```bash
review project . --config reviewagent.yml
review project . --no-enterprise
```

Project review automatically searches for ReviewAgent config files unless `--no-enterprise` is set.

## Multi-Agent Review

```bash
review project . --agents
review project . --agents quality,bug,security
```

Agents run synchronously and do not modify source files.

## LLM Review

Mock provider is offline:

```bash
review project . --llm --llm-provider mock
```

Real providers require explicit network authorization:

```bash
review project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
review project . --llm --llm-provider anthropic --allow-network --allow-llm --code-sharing summary-only
```

`--llm` alone is not permission to call external providers.

## Network Flags

```bash
--allow-network
--allow-llm
--allow-github
--code-sharing summary-only|snippets|full-context
--confirm-network
--audit-network
```

The CLI converts `summary-only` to the internal `summary_only` NetworkPolicy value.

## Dashboard Commands

```bash
review dashboard init-db
review dashboard serve --host 127.0.0.1 --port 8080
```

The Dashboard can also be started with:

```bash
reviewagent-dashboard
python -m reviewagent.dashboard.app
```

## Version

```bash
review --version
reviewagent --version
```

## Exit Codes

- `0`: command succeeded and no `--fail-on` threshold was reached
- `1`: `--fail-on` was provided and an issue at that severity or higher exists
- `2`: CLI argument or local execution error

Example:

```bash
review project . --fail-on high
```

## Troubleshooting

- Missing file or directory: returned as a normal issue when possible.
- Missing LLM key/provider: returned as an `ArchitectureReviewError` issue.
- Unknown agent: returned as an `UnknownAgent` issue.
- Output path cannot be written: exits with code `2`.
- Use `--debug` to print tracebacks to stderr. JSON stdout remains clean.
