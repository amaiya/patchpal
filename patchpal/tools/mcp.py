"""MCP (Model Context Protocol) client integration for PatchPal.

This module provides support for connecting to MCP servers and exposing their
tools to the PatchPal agent. It handles:
- Loading MCP server configurations from config files
- Establishing connections to local MCP servers (stdio transport)
- Establishing connections to remote MCP servers (SSE/HTTP transport)
- Converting MCP tool definitions to LiteLLM format
- Executing MCP tools and formatting results

Configuration is loaded from:
1. ~/.patchpal/config.json (personal config)
2. .patchpal/config.json (project config)

Example config.json for local servers:
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["python", "-m", "mcp_server_filesystem", "/allowed/path"],
      "enabled": true,
      "environment": {}
    }
  }
}

Example config.json for remote servers:
{
  "mcp": {
    "congress": {
      "type": "remote",
      "url": "https://congress-mcp-an.fastmcp.app/mcp",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer YOUR_TOKEN"
      }
    }
  }
}
"""

import asyncio
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# MCP SDK imports - these will be optional dependencies
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.types import TextContent

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def load_mcp_tools(config_path: Optional[Path] = None) -> Tuple[List[Dict], Dict]:
    """Load tools from configured MCP servers.

    Args:
        config_path: Optional path to config file. If None, searches standard locations.

    Returns:
        Tuple of (tool_schemas, tool_functions) compatible with LiteLLM format.
        Returns empty lists if MCP is not available or no servers configured.
    """
    if not MCP_AVAILABLE:
        # Check if user has MCP configured
        config = _load_mcp_config(config_path)
        if config.get("mcp"):
            print("Warning: MCP servers configured but MCP SDK not installed.")
            print("Install it with: pip install patchpal[mcp]")
        return [], {}

    try:
        return asyncio.run(_load_mcp_tools_async(config_path))
    except Exception as e:
        print(f"Warning: Failed to load MCP tools: {e}")
        return [], {}


async def _load_mcp_tools_async(config_path: Optional[Path] = None) -> Tuple[List[Dict], Dict]:
    """Async implementation of MCP tool loading."""
    config = _load_mcp_config(config_path)
    mcp_servers = config.get("mcp", {})

    if not mcp_servers:
        return [], {}

    tools = []
    functions = {}

    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            continue

        if not server_config.get("enabled", True):
            continue

        server_type = server_config.get("type", "local")
        if server_type not in ("local", "remote"):
            print(f"Warning: Unknown MCP server type '{server_type}' for server '{server_name}'")
            continue

        try:
            if server_type == "local":
                server_tools, server_functions = await _load_local_server_tools(
                    server_name, server_config
                )
            else:  # remote
                server_tools, server_functions = await _load_remote_server_tools(
                    server_name, server_config
                )

            tools.extend(server_tools)
            functions.update(server_functions)
        except Exception as e:
            print(f"Warning: Failed to load MCP server '{server_name}': {e}")
            continue

    return tools, functions


async def _load_local_server_tools(
    server_name: str, server_config: Dict[str, Any]
) -> Tuple[List[Dict], Dict]:
    """Load tools from a local MCP server (stdio transport).

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict

    Returns:
        Tuple of (tool_schemas, tool_functions)
    """
    command_parts = server_config.get("command", [])
    if not command_parts:
        raise ValueError(f"MCP server '{server_name}' missing 'command' field")

    server_params = StdioServerParameters(
        command=command_parts[0],
        args=command_parts[1:] if len(command_parts) > 1 else [],
        env=server_config.get("environment", {}),
    )

    tools = []
    functions = {}

    # Create a temporary connection to discover tools
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools from the MCP server
            tools_response = await session.list_tools()

            for mcp_tool in tools_response.tools:
                # Convert MCP tool to LiteLLM format
                tool_name = f"{server_name}_{mcp_tool.name}"
                tool_schema = _mcp_to_litellm_schema(tool_name, mcp_tool)
                tools.append(tool_schema)

                # Create executor function
                executor = _make_local_mcp_executor(server_params, mcp_tool.name)
                functions[tool_name] = executor

    return tools, functions


async def _load_remote_server_tools(
    server_name: str, server_config: Dict[str, Any]
) -> Tuple[List[Dict], Dict]:
    """Load tools from a remote MCP server (SSE/HTTP transport).

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict

    Returns:
        Tuple of (tool_schemas, tool_functions)
    """
    server_url = server_config.get("url", "")
    if not server_url:
        raise ValueError(f"MCP server '{server_name}' missing 'url' field")

    # Validate URL
    parsed = urlparse(server_url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"MCP server '{server_name}' URL must start with http:// or https://")

    # Get optional headers for authentication
    headers = server_config.get("headers", {})

    tools = []
    functions = {}

    # Create a temporary connection to discover tools
    async with sse_client(server_url, headers=headers) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()

            # List available tools from the MCP server
            tools_response = await session.list_tools()

            for mcp_tool in tools_response.tools:
                # Convert MCP tool to LiteLLM format
                tool_name = f"{server_name}_{mcp_tool.name}"
                tool_schema = _mcp_to_litellm_schema(tool_name, mcp_tool)
                tools.append(tool_schema)

                # Create executor function
                executor = _make_remote_mcp_executor(server_url, headers, mcp_tool.name)
                functions[tool_name] = executor

    return tools, functions


def _mcp_to_litellm_schema(tool_name: str, mcp_tool) -> Dict[str, Any]:
    """Convert MCP tool definition to LiteLLM format.

    Args:
        tool_name: Full tool name (server_name + tool_name)
        mcp_tool: MCP tool definition

    Returns:
        Tool schema in LiteLLM format
    """
    return {
        "type": "function",
        "function": {
            "name": tool_name,
            "description": mcp_tool.description or f"MCP tool: {tool_name}",
            "parameters": mcp_tool.inputSchema,
        },
    }


def _make_local_mcp_executor(server_params: StdioServerParameters, tool_name: str):
    """Create an executor function for a local MCP tool.

    Args:
        server_params: Server connection parameters
        tool_name: Name of the tool on the MCP server

    Returns:
        Callable that executes the tool and returns formatted result
    """

    def executor(**kwargs) -> str:
        """Execute MCP tool and return result.

        This function creates a new connection each time it's called.
        For production use, consider maintaining persistent connections.
        """
        return asyncio.run(_call_local_mcp_tool(server_params, tool_name, kwargs))

    return executor


def _make_remote_mcp_executor(server_url: str, headers: Dict[str, str], tool_name: str):
    """Create an executor function for a remote MCP tool.

    Args:
        server_url: URL of the remote MCP server
        headers: Optional HTTP headers for authentication
        tool_name: Name of the tool on the MCP server

    Returns:
        Callable that executes the tool and returns formatted result
    """

    def executor(**kwargs) -> str:
        """Execute MCP tool and return result.

        This function creates a new connection each time it's called.
        For production use, consider maintaining persistent connections.
        """
        return asyncio.run(_call_remote_mcp_tool(server_url, headers, tool_name, kwargs))

    return executor


async def _call_local_mcp_tool(
    server_params: StdioServerParameters, tool_name: str, arguments: Dict[str, Any]
) -> str:
    """Call a local MCP tool and return formatted result.

    Args:
        server_params: Server connection parameters
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Formatted tool output as string
    """
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Call the tool
            result = await session.call_tool(tool_name, arguments=arguments)

            # Format result for LLM consumption
            return _format_tool_result(result)


async def _call_remote_mcp_tool(
    server_url: str, headers: Dict[str, str], tool_name: str, arguments: Dict[str, Any]
) -> str:
    """Call a remote MCP tool and return formatted result.

    Args:
        server_url: URL of the remote MCP server
        headers: Optional HTTP headers for authentication
        tool_name: Name of the tool to call
        arguments: Tool arguments

    Returns:
        Formatted tool output as string
    """
    async with sse_client(server_url, headers=headers) as streams:
        async with ClientSession(streams[0], streams[1]) as session:
            await session.initialize()

            # Call the tool
            result = await session.call_tool(tool_name, arguments=arguments)

            # Format result for LLM consumption
            return _format_tool_result(result)


def _format_tool_result(result) -> str:
    """Format MCP tool result for LLM consumption.

    Args:
        result: MCP tool call result

    Returns:
        Formatted string output
    """
    output_parts = []

    # Extract text content from result
    for content in result.content:
        if isinstance(content, TextContent):
            output_parts.append(content.text)
        elif hasattr(content, "text"):
            output_parts.append(content.text)
        else:
            # Handle other content types if needed
            output_parts.append(str(content))

    return "\n".join(output_parts) if output_parts else "Tool executed successfully."


def _load_mcp_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load MCP configuration from file.

    Searches for config in standard locations if path not provided:
    1. ~/.patchpal/config.json (personal config)
    2. .patchpal/config.json (project config)

    Args:
        config_path: Optional explicit path to config file

    Returns:
        Configuration dict (empty if no config found)
    """
    if config_path is None:
        # Check standard locations
        candidates = [
            Path.home() / ".patchpal" / "config.json",
            Path(".patchpal") / "config.json",
        ]
        for path in candidates:
            if path.exists():
                config_path = path
                break

    if config_path and config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse MCP config at {config_path}: {e}")
            return {}

    return {}


def is_mcp_available() -> bool:
    """Check if MCP SDK is available.

    Returns:
        True if MCP SDK is installed and can be imported
    """
    return MCP_AVAILABLE
