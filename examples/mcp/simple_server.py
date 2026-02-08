#!/usr/bin/env python3
"""Simple example MCP server for PatchPal.

This demonstrates how to create a custom MCP server with a few simple tools.
You can use this as a template for building your own MCP servers.

Usage:
    python simple_server.py

Configuration in ~/.patchpal/config.json:
{
  "mcp": {
    "example": {
      "type": "local",
      "command": ["python", "examples/mcp/simple_server.py"],
      "enabled": true
    }
  }
}
"""

from mcp.server.mcpserver import MCPServer

# Create the MCP server
mcp = MCPServer("Example Server")


@mcp.tool()
def greet(name: str, style: str = "friendly") -> str:
    """Generate a greeting message.

    Args:
        name: Name of the person to greet
        style: Greeting style - 'friendly', 'formal', or 'casual'
    """
    styles = {
        "friendly": f"Hello {name}! How are you doing today?",
        "formal": f"Good day, {name}. I hope this message finds you well.",
        "casual": f"Hey {name}, what's up?",
    }
    return styles.get(style, styles["friendly"])


@mcp.tool()
def calculate(operation: str, a: float, b: float) -> str:
    """Perform basic arithmetic calculations.

    Args:
        operation: Math operation - 'add', 'subtract', 'multiply', or 'divide'
        a: First number
        b: Second number
    """
    operations = {
        "add": lambda x, y: x + y,
        "subtract": lambda x, y: x - y,
        "multiply": lambda x, y: x * y,
        "divide": lambda x, y: x / y if y != 0 else "Error: Division by zero",
    }

    if operation not in operations:
        return f"Error: Unknown operation '{operation}'. Use: add, subtract, multiply, divide"

    result = operations[operation](a, b)
    if isinstance(result, str):  # Error message
        return result
    return f"{a} {operation} {b} = {result}"


@mcp.tool()
def reverse_text(text: str) -> str:
    """Reverse a string of text.

    Args:
        text: Text to reverse
    """
    return text[::-1]


@mcp.tool()
def word_count(text: str) -> str:
    """Count words, characters, and lines in text.

    Args:
        text: Text to analyze
    """
    lines = text.split("\n")
    words = text.split()
    chars = len(text)

    return f"""Text Analysis:
- Lines: {len(lines)}
- Words: {len(words)}
- Characters: {chars}"""


if __name__ == "__main__":
    # Run the server with stdio transport (for local connections)
    mcp.run(transport="stdio")
