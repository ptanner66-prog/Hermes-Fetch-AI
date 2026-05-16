from __future__ import annotations

from typing import Any


class FakeFastMCP:
    tools = {
        "echo": {
            "name": "echo",
            "description": "Return the supplied text.",
            "inputSchema": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
        "add": {
            "name": "add",
            "description": "Add two integers.",
            "inputSchema": {
                "type": "object",
                "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
                "required": ["a", "b"],
            },
        },
    }

    async def list_tools(self) -> list[dict[str, Any]]:
        return list(self.tools.values())

    async def call_tool(self, name: str, args: dict[str, Any]) -> Any:
        if name == "echo":
            return str(args.get("text", ""))
        if name == "add":
            return int(args.get("a", 0)) + int(args.get("b", 0))
        raise ValueError(f"unknown tool: {name}")


def _build_fake_server() -> FakeFastMCP:
    return FakeFastMCP()
