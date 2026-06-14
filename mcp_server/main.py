"""Launch magicreview as an MCP stdio server.

Local Claude Desktop configuration example:

```json
{
  "mcpServers": {
    "review-agent": {
      "command": "python",
      "args": ["-m", "mcp_server.main"]
    }
  }
}
```
"""

from __future__ import annotations

import asyncio

from mcp_server.server import run_stdio_server


def main() -> None:
    """Start the magicreview MCP stdio server."""

    asyncio.run(run_stdio_server())


if __name__ == "__main__":
    main()
