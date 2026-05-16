from __future__ import annotations

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("hermes-fetch-ai-test")


@mcp.tool()
def echo(text: str) -> str:
    return text


@mcp.tool()
def add(a: int, b: int) -> int:
    return a + b


if __name__ == "__main__":
    mcp.run(transport="stdio")
