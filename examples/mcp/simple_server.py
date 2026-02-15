#!/usr/bin/env python3
"""Simple example MCP server for PatchPal.

This demonstrates how to create a custom MCP server with a few simple tools.
You can use this as a template for building your own MCP servers.

Usage:
    python simple_server.py

Configuration in ~/.patchpal/config.json:
{
  "mcp": {
    "demo": {
      "type": "local",
      "command": ["python", "examples/mcp/simple_server.py"],
      "enabled": true
    }
  }
}
"""

import asyncio
import sys

try:
    from mcp.server import NotificationOptions, Server
    from mcp.server.models import InitializationOptions
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    print("Error: MCP SDK not installed or incompatible version")
    print("Install it with: pip install 'mcp>=1.0.0'")
    sys.exit(1)


# Create an MCP server
server = Server("demo-server")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="greet",
            description="Greet a person by name",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the person to greet",
                    }
                },
                "required": ["name"],
            },
        ),
        Tool(
            name="add_numbers",
            description="Add two numbers together",
            inputSchema={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "number",
                        "description": "First number",
                    },
                    "b": {
                        "type": "number",
                        "description": "Second number",
                    },
                },
                "required": ["a", "b"],
            },
        ),
        Tool(
            name="count_words",
            description="Count words in a text string",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Text to analyze",
                    }
                },
                "required": ["text"],
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool execution."""

    if name == "greet":
        person_name = arguments.get("name", "stranger")
        result = f"Hello, {person_name}! 👋 Welcome to the MCP demo server."
        return [TextContent(type="text", text=result)]

    elif name == "add_numbers":
        a = arguments.get("a", 0)
        b = arguments.get("b", 0)
        result = a + b
        return [TextContent(type="text", text=f"The sum of {a} + {b} = {result}")]

    elif name == "count_words":
        text = arguments.get("text", "")
        words = text.split()
        lines = text.split("\n")
        chars = len(text)

        result = f"""Text Analysis:
- Lines: {len(lines)}
- Words: {len(words)}
- Characters: {chars}"""
        return [TextContent(type="text", text=result)]

    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    # Run the server using stdio transport (for local connections)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="demo-server",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
