"""magicreview MCP server over stdio.

The preferred runtime uses the official ``mcp`` Python SDK. When the SDK is
not installed, this module falls back to a compact JSON-RPC stdio loop that is
useful for local smoke tests and keeps the process importable.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from typing import Any

from mcp_server.tools import call_review_tool, error_report, list_review_tools


SERVER_NAME = "review-agent-mcp"
logger = logging.getLogger(__name__)


try:
    import mcp.types as mcp_types
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
except ModuleNotFoundError:
    mcp_types = None
    Server = None
    stdio_server = None


def create_server() -> Any:
    """Create and configure the official MCP Server instance."""

    if Server is None or mcp_types is None:
        return None

    server = Server(SERVER_NAME)

    @server.list_tools()
    async def handle_list_tools() -> list[Any]:
        return [
            mcp_types.Tool(
                name=tool.name,
                description=tool.description,
                inputSchema=tool.input_schema,
            )
            for tool in list_review_tools()
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any] | None) -> list[Any]:
        try:
            payload = await call_review_tool(name, arguments)
        except Exception as exc:
            logger.exception("Unhandled MCP tool failure for %s.", name)
            payload = error_report(str(exc))
        return [mcp_types.TextContent(type="text", text=payload)]

    return server


async def run_stdio_server() -> None:
    """Run the magicreview MCP server over stdio."""

    _configure_logging()
    server = create_server()
    if server is None or stdio_server is None:
        logger.warning("Official mcp SDK is not installed; using JSON-RPC fallback stdio loop.")
        await run_json_rpc_stdio_fallback()
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


async def run_json_rpc_stdio_fallback() -> None:
    """Run a minimal JSON-RPC line protocol for environments without ``mcp``."""

    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if line == "":
            return
        if not line.strip():
            continue

        response = await _handle_json_rpc_line(line)
        sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
        sys.stdout.flush()


async def _handle_json_rpc_line(line: str) -> dict[str, Any]:
    try:
        request = json.loads(line)
    except json.JSONDecodeError as exc:
        return _json_rpc_error(None, -32700, f"Parse error: {exc.msg}")

    request_id = request.get("id")
    method = request.get("method")
    params = request.get("params") if isinstance(request.get("params"), dict) else {}

    try:
        match method:
            case "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {"name": SERVER_NAME, "version": "0.1.0"},
                    "capabilities": {"tools": {}},
                }
            case "tools/list":
                result = {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.input_schema,
                        }
                        for tool in list_review_tools()
                    ]
                }
            case "tools/call":
                name = params.get("name")
                arguments = params.get("arguments")
                if not isinstance(name, str):
                    raise ValueError("tools/call requires a string `name` parameter.")
                if arguments is not None and not isinstance(arguments, dict):
                    raise ValueError("tools/call `arguments` must be an object when provided.")
                text = await call_review_tool(name, arguments)
                result = {"content": [{"type": "text", "text": text}]}
            case _:
                return _json_rpc_error(request_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        logger.exception("JSON-RPC fallback request failed.")
        result = {"content": [{"type": "text", "text": error_report(str(exc))}], "isError": True}

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _json_rpc_error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
