# Enterprise Rule Center

Phase 5.5 adds configurable enterprise rules on top of MagicReview's built-in
static analyzers.

It lets teams encode local coding standards in YAML or JSON and run them during
`mgreview project`, optional `mgreview file`, and MCP `review_project` calls.

## Config files

Automatic search order inside the project root:

1. `magicreview.yml`
2. `magicreview.yaml`
3. `magicreview.json`
4. `.magicreview.yml`
5. `.magicreview.yaml`
6. `.magicreview.json`

Explicit config paths can be passed with CLI or MCP.

## YAML example

```yaml
rules:
  max_function_length:
    enabled: true
    max_lines: 80
    severity: medium

  no_select_star:
    enabled: true
    severity: high

  forbidden_imports:
    enabled: true
    imports:
      - os.system
      - subprocess.Popen
    severity: high
```

## Built-in rules

- `max_function_length`: flags functions longer than the configured line count.
- `max_parameters`: flags functions with too many parameters, skipping `self` and `cls`.
- `no_select_star`: forbids SQL `SELECT *`.
- `no_controller_repository`: prevents controller/API/router files from directly depending on repository or DB layers.
- `service_log_required`: requires logging in public service functions and methods.
- `forbidden_imports`: flags forbidden imports or API calls.
- `layer_rules`: enforces configured layer dependency direction.

## CLI

Auto-discover config:

```bash
python -m magicreview.cli.main project examples/enterprise_policy_project
```

Explicit config:

```bash
python -m magicreview.cli.main project examples/enterprise_policy_project --config examples/enterprise_policy_project/magicreview.yml
```

Disable enterprise rules:

```bash
python -m magicreview.cli.main project examples/enterprise_policy_project --no-enterprise
```

Combine with LLM architecture review:

```bash
python -m magicreview.cli.main project examples/enterprise_policy_project --config examples/enterprise_policy_project/magicreview.yml --llm --llm-provider mock
```

## MCP

```json
{
  "path": "examples/enterprise_policy_project",
  "config_path": "examples/enterprise_policy_project/magicreview.yml",
  "enable_enterprise_rules": true
}
```

## Security

- YAML is loaded with `yaml.safe_load`.
- Config content is never executed.
- Automatic search only checks known config filenames inside the project root.
- Config files larger than 1MB are rejected.
- Config errors are returned as `EnterpriseRuleConfigError` issues.

## Boundaries

Phase 5.5 is a local configurable rule center. Remote rule markets, enterprise
knowledge bases, and multi-agent policy workflows are reserved for later phases.



