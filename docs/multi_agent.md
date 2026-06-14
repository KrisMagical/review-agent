# Phase 6 Multi-Agent Review

Phase 6 adds a synchronous multi-agent review layer on top of the existing MagicReview analyzers. It does not replace the Phase 1-5.5 pipeline; it is enabled only when requested.

## Coordinator

`ReviewCoordinator` builds an `AgentContext`, runs selected agents in order, catches agent failures, then deduplicates and sorts issues into the standard JSON shape:

```json
{
  "issues": []
}
```

Default order:

1. KnowledgeAgent
2. QualityAgent
3. BugAgent
4. SecurityAgent
5. ArchitectureAgent
6. RefactorAgent

## Agents

- `QualityAgent`: quality rules, Ruff, Radon, type hints, magic numbers, function length, parameters.
- `BugAgent`: None risk, KeyError, IndexError, ZeroDivision, file leak, mutable defaults, broad exceptions, unsafe deserialization.
- `SecurityAgent`: SQL injection, path traversal, hardcoded secrets, weak JWT secrets, command injection.
- `ArchitectureAgent`: import graph cycles, high coupling, God Object, FastAPI architecture checks, optional LLM architecture review.
- `KnowledgeAgent`: YAML/JSON enterprise rules from Phase 5.5.
- `RefactorAgent`: suggestion-only recommendations derived from accumulated issues. It never edits files.

## CLI

```bash
python -m magicreview.cli.main project examples/multi_agent_project --agents
python -m magicreview.cli.main project examples/multi_agent_project --agents quality,security
python -m magicreview.cli.main project examples/multi_agent_project --agents --config examples/multi_agent_project/magicreview.yml
python -m magicreview.cli.main project examples/multi_agent_project --agents --llm --llm-provider mock
```

`--agents` without a value runs all agents. A comma-separated value runs only that subset.

## MCP

`review_project` accepts:

```json
{
  "path": "examples/multi_agent_project",
  "enable_agents": true,
  "agents": ["quality", "security"],
  "config_path": "examples/multi_agent_project/magicreview.yml",
  "enable_enterprise_rules": true,
  "enable_llm": false
}
```

## Relationship To Phase 5

LLM architecture review remains opt-in. `ArchitectureAgent` calls it only when `enable_llm=true`.

## Relationship To Phase 5.5

`KnowledgeAgent` loads and executes enterprise rules. Disable it with `enable_enterprise_rules=false` or omit `knowledge` from the selected agent list.

## Limits

The scheduler is synchronous and local. Agents do not persist state, write source files, call remote rule markets, open pull requests, or run code from the reviewed project. Phase 7+ can add richer orchestration, GitHub workflows, dashboards, and persistent governance data.



