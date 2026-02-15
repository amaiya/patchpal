"""Test StreamableHTTP transport for BioARxiv MCP server."""

import asyncio

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def test_biorxiv():
    """Test connecting to BioARxiv MCP server using StreamableHTTP."""
    server_url = "https://mcp.deepsense.ai/biorxiv/mcp"

    print(f"Testing StreamableHTTP connection to: {server_url}")

    try:
        async with streamablehttp_client(server_url) as streams:
            read_stream, write_stream, get_session_id = streams
            print("✓ StreamableHTTP client created successfully")
            print(f"  Session ID callback: {get_session_id}")

            async with ClientSession(read_stream, write_stream) as session:
                print("✓ ClientSession created")

                # Initialize
                await session.initialize()
                print("✓ Session initialized")

                # List tools
                tools_response = await session.list_tools()
                print(f"✓ Found {len(tools_response.tools)} tools:")
                for tool in tools_response.tools:
                    print(f"  - {tool.name}: {tool.description}")

                print("\n✅ SUCCESS: BioARxiv MCP server is working!")

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_biorxiv())
