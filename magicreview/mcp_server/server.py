"""magicreview MCP stdio server."""

from __future__ import annotations

from typing import Any, Callable

from magicreview.mcp_server import tools


try:
    from mcp.server.fastmcp import FastMCP
except ModuleNotFoundError:  # pragma: no cover - only used when mcp is absent
    class FastMCP:  # type: ignore[no-redef]
        """Small import-time fallback that keeps tests and docs usable."""

        def __init__(self, name: str) -> None:
            self.name = name
            self.registered_tools: dict[str, Callable[..., Any]] = {}

        def tool(self) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                self.registered_tools[func.__name__] = func
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError("The Python 'mcp' package is required to run the MCP server.")


mcp = FastMCP("MagicReview")


@mcp.tool()
def review_file(path: str, config_path: str | None = None) -> dict[str, Any]:
    """Review a single Python file and return magicreview issues."""

    return tools.review_file(path, config_path=config_path)


@mcp.tool()
def review_project(
    path: str,
    enable_llm: bool = False,
    llm_provider: str | None = None,
    config_path: str | None = None,
    enable_enterprise_rules: bool = True,
    enable_agents: bool = False,
    agents: list[str] | None = None,
    network_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Review a Python project and return magicreview issues."""

    return tools.review_project(
        path,
        enable_llm=enable_llm,
        llm_provider=llm_provider,
        config_path=config_path,
        enable_enterprise_rules=enable_enterprise_rules,
        enable_agents=enable_agents,
        agents=agents,
        network_policy=network_policy,
    )


@mcp.tool()
def review_diff(diff: str) -> dict[str, Any]:
    """Review a git diff or patch and return magicreview issues."""

    return tools.review_diff(diff)


def main() -> None:
    """Start the MCP stdio server."""

    mcp.run()


if __name__ == "__main__":
    main()
