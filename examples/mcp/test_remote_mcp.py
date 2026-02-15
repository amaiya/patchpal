#!/usr/bin/env python3
"""Test script for remote MCP server connectivity.

This script tests connecting to the congress.gov MCP server
and lists available tools.

Usage:
    python examples/mcp/test_remote_mcp.py
"""

import asyncio
import sys
from pathlib import Path

# Add patchpal to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client
except ImportError:
    print("Error: MCP SDK not installed")
    print("Install it with: pip install patchpal[mcp]")
    sys.exit(1)


async def test_congress_mcp():
    """Test connection to congress.gov MCP server."""
    server_url = "https://congress-mcp-an.fastmcp.app/mcp"

    print(f"Connecting to {server_url}...")

    try:
        async with sse_client(server_url) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("✓ Connected successfully!\n")

                # List tools
                tools_response = await session.list_tools()
                print(f"Available tools ({len(tools_response.tools)}):")
                for tool in tools_response.tools:
                    print(f"  • {tool.name}")
                    if tool.description:
                        desc = tool.description[:80]
                        if len(tool.description) > 80:
                            desc += "..."
                        print(f"    {desc}")

                # List resources if any
                resources_response = await session.list_resources()
                if resources_response.resources:
                    print(f"\nAvailable resources ({len(resources_response.resources)}):")
                    for resource in resources_response.resources:
                        print(f"  • {resource.uri}")

                print("\n✓ Test successful! Congress.gov MCP server is accessible.")
                return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("\nTroubleshooting:")
        print("1. Check your internet connection")
        print("2. Verify the server URL is correct")
        print("3. Try accessing the URL in a browser")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_congress_mcp())
    sys.exit(0 if success else 1)
