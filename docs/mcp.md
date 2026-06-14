# MCP Server

MagicReview exposes local review tools through an MCP stdio server.

## MCP stdio Server

Start:

```bash
mgreview-mcp
```

Alternative:

```bash
python -m magicreview.mcp_server.server
```

MCP uses stdio. It does not start an HTTP server.

## Local Usage

Use MCP when you want an AI coding tool to call MagicReview locally against files, diffs, or projects.

MagicReview remains offline by default. Optional LLM/network behavior requires explicit arguments.

## Cursor Config

```json
{
  "mcpServers": {
    "MagicReview": {
      "command": "mgreview-mcp"
    }
  }
}
```

Source checkout alternative:

```json
{
  "mcpServers": {
    "MagicReview": {
      "command": "python",
      "args": ["-m", "magicreview.mcp_server.server"],
      "cwd": "/path/to/review-agent"
    }
  }
}
```

## Claude Desktop Config

```json
{
  "mcpServers": {
    "MagicReview": {
      "command": "mgreview-mcp"
    }
  }
}
```

## review_file

Input:

```json
{"path": "examples/bad_code.py"}
```

Output:

```json
{"issues": []}
```

## review_diff

Input:

```json
{"diff": "diff --git a/a.py b/a.py\n..."}
```

Output:

```json
{"issues": []}
```

## review_project

Input:

```json
{"path": "examples/phase2_bad_project"}
```

Output:

```json
{"issues": []}
```

## enable_llm

Mock provider stays offline:

```json
{
  "path": "examples/architecture_bad_project",
  "enable_llm": true,
  "llm_provider": "mock"
}
```

Real provider with explicit policy:

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

## enable_agents

```json
{
  "path": "examples/multi_agent_project",
  "enable_agents": true
}
```

Selected agents:

```json
{
  "path": "examples/multi_agent_project",
  "enable_agents": true,
  "agents": ["quality", "security"]
}
```

## Enterprise Config

```json
{
  "path": "examples/enterprise_policy_project",
  "config_path": "examples/enterprise_policy_project/magicreview.yml",
  "enable_enterprise_rules": true
}
```

Disable:

```json
{"path": ".", "enable_enterprise_rules": false}
```

## network_policy

Accepted fields include:

- `enabled`
- `allow_llm`
- `allow_github_api`
- `allow_remote_mcp`
- `code_sharing_mode`
- `allowed_providers`
- `audit_enabled`

Without `network_policy`, MCP remains offline.

## Offline Default

MCP does not call real LLM providers by default. It never modifies reviewed source files.

## Docker MCP Note

```bash
docker run --rm -i magicreview mgreview-mcp
```

Docker MCP is suitable for advanced local integrations where stdio can be connected to the tool.

## Troubleshooting

- Missing dependency: install `pip install -e ".[mcp]"` or `".[all]"`.
- Large projects: MagicReview returns safe issue JSON instead of crashing.
- Real LLM blocked: provide `network_policy`.
- MCP is not HTTP; configure tools for stdio.
- Remote/hosted MCP is a future or advanced deployment pattern.




