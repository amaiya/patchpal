#!/usr/bin/env python3
"""Debug script for MCP connection issues."""

import asyncio
import sys
import traceback
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


async def test_notion_mcp_detailed():
    """Test connection to Notion MCP server with detailed error info."""
    server_url = "https://mcp.deepsense.ai/biorxiv/mcp"

    print(f"Connecting to {server_url}...")
    print(f"Python version: {sys.version}")
    print()

    try:
        print("Step 1: Opening SSE client connection...")
        async with sse_client(server_url) as streams:
            print("✓ SSE client opened")

            print("Step 2: Creating client session...")
            async with ClientSession(streams[0], streams[1]) as session:
                print("✓ Client session created")

                print("Step 3: Initializing session...")
                await session.initialize()
                print("✓ Session initialized")

                print("\nStep 4: Listing tools...")
                tools_response = await session.list_tools()
                print(f"✓ Found {len(tools_response.tools)} tools:")
                for tool in tools_response.tools[:5]:
                    print(f"  - {tool.name}")

                print("\n✓ Connection test successful!")
                return True

    except Exception as e:
        print(f"\n✗ Error: {type(e).__name__}: {e}")
        print("\nFull traceback:")
        traceback.print_exc()

        # Try to get more details
        if hasattr(e, "__cause__") and e.__cause__:
            print(f"\nCaused by: {type(e.__cause__).__name__}: {e.__cause__}")

        if hasattr(e, "exceptions"):
            print(f"\nException group contains {len(e.exceptions)} exception(s):")
            for i, exc in enumerate(e.exceptions, 1):
                print(f"\n  Exception {i}: {type(exc).__name__}: {exc}")
                if hasattr(exc, "__traceback__"):
                    print("  Traceback:")
                    traceback.print_tb(exc.__traceback__)

        return False


if __name__ == "__main__":
    success = asyncio.run(test_notion_mcp_detailed())
    sys.exit(0 if success else 1)
