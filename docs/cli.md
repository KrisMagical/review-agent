# CLI

The `mgreview` CLI is the quickest way to use MagicReview locally. It calls the same ReviewService used by MCP, GitHub App, Dashboard, enterprise rules, LLM review, and multi-agent review.

## Install

```bash
pip install -e ".[all]"
mgreview --help
mgreview --version
```

Run without console scripts:

```bash
python -m magicreview.cli.main --help
```

## mgreview file

```bash
mgreview file examples/bad_code.py
mgreview file examples/bad_code.py --format terminal
mgreview file examples/bad_code.py --format json --fail-on high
mgreview file examples/bad_code.py --config magicreview.yml
mgreview file examples/bad_code.py --save
```

`--config` enables explicit enterprise YAML/JSON rules for the file review path when supported by the rule.

## mgreview diff

`mgreview diff` reads unified diff text from stdin by default:

```bash
git diff | mgreview diff --format terminal
cat examples/sample.diff | mgreview diff --format json
```

Read a patch file:

```bash
mgreview diff --file examples/sample.diff --format markdown --output diff-review.md
mgreview diff --file examples/sample.diff --save
```

## mgreview project

```bash
mgreview project .
mgreview project . --format terminal
mgreview project examples/phase2_bad_project --format markdown --output review.md
mgreview project examples/enterprise_policy_project --config examples/enterprise_policy_project/magicreview.yml
mgreview project examples/multi_agent_project --agents
mgreview project examples/multi_agent_project --agents quality,security
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
mgreview project . --format html --output review.html
mgreview diff --file changes.patch --format markdown --output review.md
```

## Filtering And Limits

```bash
mgreview project . --severity high
mgreview project . --max-issues 50
```

`--severity high` shows only `high` and `critical` issues.

## Save Results

Saving is opt-in:

```bash
mgreview project . --save
mgreview file app/main.py --save
mgreview diff --file changes.patch --save
```

Saved results go to SQLite at `MGREVIEW_DB_PATH` or `.magicreview/magicreview.db`.

## Enterprise Rules

```bash
mgreview project . --config magicreview.yml
mgreview project . --no-enterprise
```

Project review automatically searches for MagicReview config files unless `--no-enterprise` is set.

## Multi-Agent Review

```bash
mgreview project . --agents
mgreview project . --agents quality,bug,security
```

Agents run synchronously and do not modify source files.

## LLM Review

Mock provider is offline:

```bash
mgreview project . --llm --llm-provider mock
```

Real providers require explicit network authorization:

```bash
mgreview project . --llm --llm-provider openai --allow-network --allow-llm --code-sharing summary-only
mgreview project . --llm --llm-provider anthropic --allow-network --allow-llm --code-sharing summary-only
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
mgreview dashboard init-db
mgreview dashboard serve --host 127.0.0.1 --port 8080
```

The Dashboard can also be started with:

```bash
mgreview-dashboard
python -m magicreview.dashboard.app
```

## Version

```bash
mgreview --version
mgreview --version
```

## Exit Codes

- `0`: command succeeded and no `--fail-on` threshold was reached
- `1`: `--fail-on` was provided and an issue at that severity or higher exists
- `2`: CLI argument or local execution error

Example:

```bash
mgreview project . --fail-on high
```

## Troubleshooting

- Missing file or directory: returned as a normal issue when possible.
- Missing LLM key/provider: returned as an `ArchitectureReviewError` issue.
- Unknown agent: returned as an `UnknownAgent` issue.
- Output path cannot be written: exits with code `2`.
- Use `--debug` to print tracebacks to stderr. JSON stdout remains clean.




