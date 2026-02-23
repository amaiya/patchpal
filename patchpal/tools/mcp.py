"""MCP (Model Context Protocol) client integration for PatchPal.

This module provides support for connecting to MCP servers and exposing their
tools to the PatchPal agent. It handles:
- Loading MCP server configurations from config files
- Establishing connections to local MCP servers (stdio transport)
- Establishing connections to remote MCP servers (SSE/HTTP transport)
- Converting MCP tool definitions to LiteLLM format
- Executing MCP tools and formatting results
- Environment variable expansion in configuration files
- Listing and accessing MCP resources
- Listing and executing MCP prompts

Configuration is loaded and merged from:
1. ~/.patchpal/mcp-config.json (global config)
2. .patchpal/mcp-config.json (project config - overrides global by server name)

Example mcp-config.json for local servers:
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["python", "-m", "mcp_server_filesystem", "/allowed/path"],
      "enabled": true,
      "environment": {
        "API_KEY": "${MY_API_KEY}"
      }
    }
  }
}

Example mcp-config.json for remote servers with environment variables:
{
  "mcp": {
    "congress": {
      "type": "remote",
      "url": "${CONGRESS_API_URL:-https://congress-mcp-an.fastmcp.app/mcp}",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer ${CONGRESS_API_KEY}"
      }
    }
  }
}

Environment variable syntax:
- ${VAR} - Expands to the value of environment variable VAR
- ${VAR:-default} - Expands to VAR if set, otherwise uses "default"
"""

import asyncio
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

# MCP SDK imports - these will be optional dependencies
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.sse import sse_client
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamablehttp_client
    from mcp.types import TextContent

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Define stub types for type hints when MCP is not available
    StdioServerParameters = Any  # type: ignore
    ClientSession = Any  # type: ignore
    TextContent = Any  # type: ignore


# Module-level cache for MCP server connection parameters
_server_configs: Dict[str, Dict[str, Any]] = {}


def _expand_env_var(value: str) -> str:
    """Expand environment variables in a string.

    Supports:
    - ${VAR} - Expands to the value of environment variable VAR
    - ${VAR:-default} - Expands to VAR if set, otherwise uses "default"

    Args:
        value: String that may contain environment variable references

    Returns:
        String with environment variables expanded

    Raises:
        ValueError: If a required environment variable is not set and has no default
    """
    # Pattern matches ${VAR} or ${VAR:-default}
    pattern = r"\$\{([^}:]+)(?::-([^}]*))?\}"

    def replace_var(match):
        var_name = match.group(1)
        default_value = match.group(2)  # Will be None if no default specified

        # Try to get the environment variable
        env_value = os.environ.get(var_name)

        if env_value is not None:
            return env_value
        elif default_value is not None:
            return default_value
        else:
            raise ValueError(
                f"Environment variable '{var_name}' is not set and has no default value. "
                f"Set the variable or use ${{VAR:-default}} syntax."
            )

    return re.sub(pattern, replace_var, value)


def _expand_env_vars_in_value(value: Any) -> Any:
    """Recursively expand environment variables in config values.

    Args:
        value: Config value (can be string, list, dict, or other type)

    Returns:
        Value with environment variables expanded
    """
    if isinstance(value, str):
        return _expand_env_var(value)
    elif isinstance(value, list):
        return [_expand_env_vars_in_value(item) for item in value]
    elif isinstance(value, dict):
        return {key: _expand_env_vars_in_value(val) for key, val in value.items()}
    else:
        # For other types (int, bool, None, etc.), return as-is
        return value


def _expand_env_vars_in_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Expand environment variables in MCP server configuration.

    Expands variables in:
    - command and args (for local servers)
    - url (for remote servers)
    - headers (for authentication)
    - environment variables

    Args:
        config: MCP server configuration dict

    Returns:
        Configuration with environment variables expanded
    """
    return _expand_env_vars_in_value(config)


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
        # Check if there's already a running event loop (e.g., in Jupyter)
        try:
            asyncio.get_running_loop()
            # We're in an async context (like Jupyter), create a task instead
            import nest_asyncio

            nest_asyncio.apply()
            return asyncio.run(_load_mcp_tools_async(config_path))
        except ImportError:
            # nest_asyncio not available, fall back to creating task
            print(
                "Warning: Running in async context without nest_asyncio. Install with: pip install nest-asyncio"
            )
            return [], {}
        except RuntimeError:
            # No running loop, safe to use asyncio.run normally
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

    # Clear and rebuild server configs cache
    global _server_configs
    _server_configs = {}

    for server_name, server_config in mcp_servers.items():
        if not isinstance(server_config, dict):
            continue

        if not server_config.get("enabled", True):
            continue

        # Expand environment variables in the server config
        try:
            server_config = _expand_env_vars_in_config(server_config)
        except ValueError as e:
            print(
                f"Warning: Failed to expand environment variables for MCP server '{server_name}': {e}"
            )
            continue

        server_type = server_config.get("type", "local")
        if server_type not in ("local", "remote"):
            print(f"Warning: Unknown MCP server type '{server_type}' for server '{server_name}'")
            continue

        # Cache the expanded config for later use (resources, prompts)
        _server_configs[server_name] = server_config

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
        server_config: Server configuration dict (with env vars already expanded)

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
                # Mark this as an MCP tool for display purposes
                executor.__mcp_server__ = server_name
                functions[tool_name] = executor

    # Give subprocess time to clean up properly
    await asyncio.sleep(0.1)

    return tools, functions


async def _load_remote_server_tools(
    server_name: str, server_config: Dict[str, Any]
) -> Tuple[List[Dict], Dict]:
    """Load tools from a remote MCP server (StreamableHTTP or SSE transport).

    Tries StreamableHTTP first, then falls back to SSE transport.

    Args:
        server_name: Name of the MCP server
        server_config: Server configuration dict (with env vars already expanded)

    Returns:
        Tuple of (tool_schemas, tool_functions)

    Raises:
        ValueError: If both transports fail to connect
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
    last_error = None

    # Try StreamableHTTP transport first (preferred)
    try:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # List available tools from the MCP server
                tools_response = await session.list_tools()

                for mcp_tool in tools_response.tools:
                    # Convert MCP tool to LiteLLM format
                    tool_name = f"{server_name}_{mcp_tool.name}"
                    tool_schema = _mcp_to_litellm_schema(tool_name, mcp_tool)
                    tools.append(tool_schema)

                    # Create executor function (StreamableHTTP)
                    executor = _make_remote_mcp_executor(
                        server_url, headers, mcp_tool.name, use_streamable_http=True
                    )
                    # Mark this as an MCP tool for display purposes
                    executor.__mcp_server__ = server_name
                    functions[tool_name] = executor

        return tools, functions
    except Exception as e:
        last_error = e
        print(
            f"StreamableHTTP transport failed for '{server_name}' ({server_url}): {e}. Trying SSE..."
        )

    # Fallback to SSE transport
    try:
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

                    # Create executor function (SSE)
                    executor = _make_remote_mcp_executor(
                        server_url, headers, mcp_tool.name, use_streamable_http=False
                    )
                    # Mark this as an MCP tool for display purposes
                    executor.__mcp_server__ = server_name
                    functions[tool_name] = executor

        return tools, functions
    except Exception as e:
        raise ValueError(
            f"Both transports failed for '{server_name}': StreamableHTTP: {last_error}, SSE: {e}"
        )


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


def _make_remote_mcp_executor(
    server_url: str, headers: Dict[str, str], tool_name: str, use_streamable_http: bool = True
):
    """Create an executor function for a remote MCP tool.

    Args:
        server_url: URL of the remote MCP server
        headers: Optional HTTP headers for authentication
        tool_name: Name of the tool on the MCP server
        use_streamable_http: If True, use StreamableHTTP transport; else use SSE

    Returns:
        Callable that executes the tool and returns formatted result
    """

    def executor(**kwargs) -> str:
        """Execute MCP tool and return result.

        This function creates a new connection each time it's called.
        For production use, consider maintaining persistent connections.
        """
        return asyncio.run(
            _call_remote_mcp_tool(server_url, headers, tool_name, kwargs, use_streamable_http)
        )

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
    server_url: str,
    headers: Dict[str, str],
    tool_name: str,
    arguments: Dict[str, Any],
    use_streamable_http: bool = True,
) -> str:
    """Call a remote MCP tool and return formatted result.

    Args:
        server_url: URL of the remote MCP server
        headers: Optional HTTP headers for authentication
        tool_name: Name of the tool to call
        arguments: Tool arguments
        use_streamable_http: If True, use StreamableHTTP transport; else use SSE

    Returns:
        Formatted tool output as string
    """
    if use_streamable_http:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Call the tool
                result = await session.call_tool(tool_name, arguments=arguments)

                # Format result for LLM consumption
                return _format_tool_result(result)
    else:
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


def list_mcp_resources() -> List[Dict[str, Any]]:
    """List all available resources from connected MCP servers.

    Returns:
        List of resource dictionaries with keys:
        - server: Server name
        - uri: Resource URI
        - name: Resource name (if provided)
        - description: Resource description (if provided)
        - mimeType: Resource MIME type (if provided)
    """
    if not MCP_AVAILABLE:
        return []

    try:
        return asyncio.run(_list_mcp_resources_async())
    except Exception as e:
        print(f"Warning: Failed to list MCP resources: {e}")
        return []


async def _list_mcp_resources_async() -> List[Dict[str, Any]]:
    """Async implementation of resource listing."""
    resources = []

    for server_name, server_config in _server_configs.items():
        try:
            server_type = server_config.get("type", "local")

            if server_type == "local":
                server_resources = await _list_local_server_resources(server_name, server_config)
            else:
                server_resources = await _list_remote_server_resources(server_name, server_config)

            resources.extend(server_resources)
        except Exception as e:
            print(f"Warning: Failed to list resources from MCP server '{server_name}': {e}")
            continue

    return resources


async def _list_local_server_resources(
    server_name: str, server_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """List resources from a local MCP server."""
    command_parts = server_config.get("command", [])
    server_params = StdioServerParameters(
        command=command_parts[0],
        args=command_parts[1:] if len(command_parts) > 1 else [],
        env=server_config.get("environment", {}),
    )

    resources = []
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            resources_response = await session.list_resources()

            for resource in resources_response.resources:
                resources.append(
                    {
                        "server": server_name,
                        "uri": resource.uri,
                        "name": getattr(resource, "name", None),
                        "description": getattr(resource, "description", None),
                        "mimeType": getattr(resource, "mimeType", None),
                    }
                )

    return resources


async def _list_remote_server_resources(
    server_name: str, server_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """List resources from a remote MCP server."""
    server_url = server_config.get("url", "")
    headers = server_config.get("headers", {})

    resources = []

    # Try StreamableHTTP first
    try:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                resources_response = await session.list_resources()

                for resource in resources_response.resources:
                    resources.append(
                        {
                            "server": server_name,
                            "uri": resource.uri,
                            "name": getattr(resource, "name", None),
                            "description": getattr(resource, "description", None),
                            "mimeType": getattr(resource, "mimeType", None),
                        }
                    )

        return resources
    except Exception:
        # Fallback to SSE
        async with sse_client(server_url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                resources_response = await session.list_resources()

                for resource in resources_response.resources:
                    resources.append(
                        {
                            "server": server_name,
                            "uri": resource.uri,
                            "name": getattr(resource, "name", None),
                            "description": getattr(resource, "description", None),
                            "mimeType": getattr(resource, "mimeType", None),
                        }
                    )

        return resources


def read_mcp_resource(server_name: str, uri: str) -> str:
    """Read content from an MCP resource.

    Args:
        server_name: Name of the MCP server
        uri: Resource URI

    Returns:
        Resource content as string
    """
    if not MCP_AVAILABLE:
        raise ValueError("MCP SDK not available")

    if server_name not in _server_configs:
        raise ValueError(f"MCP server '{server_name}' not found")

    try:
        return asyncio.run(_read_mcp_resource_async(server_name, uri))
    except Exception as e:
        raise ValueError(f"Failed to read resource: {e}")


async def _read_mcp_resource_async(server_name: str, uri: str) -> str:
    """Async implementation of resource reading."""
    server_config = _server_configs[server_name]
    server_type = server_config.get("type", "local")

    if server_type == "local":
        return await _read_local_server_resource(server_config, uri)
    else:
        return await _read_remote_server_resource(server_config, uri)


async def _read_local_server_resource(server_config: Dict[str, Any], uri: str) -> str:
    """Read resource from a local MCP server."""
    command_parts = server_config.get("command", [])
    server_params = StdioServerParameters(
        command=command_parts[0],
        args=command_parts[1:] if len(command_parts) > 1 else [],
        env=server_config.get("environment", {}),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.read_resource(uri)
            return _format_tool_result(result)


async def _read_remote_server_resource(server_config: Dict[str, Any], uri: str) -> str:
    """Read resource from a remote MCP server."""
    server_url = server_config.get("url", "")
    headers = server_config.get("headers", {})

    # Try StreamableHTTP first
    try:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.read_resource(uri)
                return _format_tool_result(result)
    except Exception:
        # Fallback to SSE
        async with sse_client(server_url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.read_resource(uri)
                return _format_tool_result(result)


def list_mcp_prompts() -> List[Dict[str, Any]]:
    """List all available prompts from connected MCP servers.

    Returns:
        List of prompt dictionaries with keys:
        - server: Server name
        - name: Prompt name
        - description: Prompt description (if provided)
        - arguments: List of argument definitions
    """
    if not MCP_AVAILABLE:
        return []

    try:
        return asyncio.run(_list_mcp_prompts_async())
    except Exception as e:
        print(f"Warning: Failed to list MCP prompts: {e}")
        return []


async def _list_mcp_prompts_async() -> List[Dict[str, Any]]:
    """Async implementation of prompt listing."""
    prompts = []

    for server_name, server_config in _server_configs.items():
        try:
            server_type = server_config.get("type", "local")

            if server_type == "local":
                server_prompts = await _list_local_server_prompts(server_name, server_config)
            else:
                server_prompts = await _list_remote_server_prompts(server_name, server_config)

            prompts.extend(server_prompts)
        except Exception as e:
            print(f"Warning: Failed to list prompts from MCP server '{server_name}': {e}")
            continue

    return prompts


async def _list_local_server_prompts(
    server_name: str, server_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """List prompts from a local MCP server."""
    command_parts = server_config.get("command", [])
    server_params = StdioServerParameters(
        command=command_parts[0],
        args=command_parts[1:] if len(command_parts) > 1 else [],
        env=server_config.get("environment", {}),
    )

    prompts = []
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            prompts_response = await session.list_prompts()

            for prompt in prompts_response.prompts:
                prompts.append(
                    {
                        "server": server_name,
                        "name": prompt.name,
                        "description": getattr(prompt, "description", None),
                        "arguments": [
                            {
                                "name": arg.name,
                                "description": getattr(arg, "description", None),
                                "required": getattr(arg, "required", False),
                            }
                            for arg in getattr(prompt, "arguments", [])
                        ],
                    }
                )

    return prompts


async def _list_remote_server_prompts(
    server_name: str, server_config: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """List prompts from a remote MCP server."""
    server_url = server_config.get("url", "")
    headers = server_config.get("headers", {})

    prompts = []

    # Try StreamableHTTP first
    try:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                prompts_response = await session.list_prompts()

                for prompt in prompts_response.prompts:
                    prompts.append(
                        {
                            "server": server_name,
                            "name": prompt.name,
                            "description": getattr(prompt, "description", None),
                            "arguments": [
                                {
                                    "name": arg.name,
                                    "description": getattr(arg, "description", None),
                                    "required": getattr(arg, "required", False),
                                }
                                for arg in getattr(prompt, "arguments", [])
                            ],
                        }
                    )

        return prompts
    except Exception:
        # Fallback to SSE
        async with sse_client(server_url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                prompts_response = await session.list_prompts()

                for prompt in prompts_response.prompts:
                    prompts.append(
                        {
                            "server": server_name,
                            "name": prompt.name,
                            "description": getattr(prompt, "description", None),
                            "arguments": [
                                {
                                    "name": arg.name,
                                    "description": getattr(arg, "description", None),
                                    "required": getattr(arg, "required", False),
                                }
                                for arg in getattr(prompt, "arguments", [])
                            ],
                        }
                    )

        return prompts


def get_mcp_prompt(server_name: str, prompt_name: str, arguments: Dict[str, Any] = None) -> str:
    """Retrieve and execute an MCP prompt.

    Args:
        server_name: Name of the MCP server
        prompt_name: Name of the prompt to execute
        arguments: Dictionary of arguments required by the prompt

    Returns:
        Formatted prompt content as string

    Raises:
        ValueError: If server not found or prompt execution fails
    """
    if not MCP_AVAILABLE:
        raise ValueError("MCP SDK not available")

    if server_name not in _server_configs:
        raise ValueError(f"MCP server '{server_name}' not found")

    try:
        return asyncio.run(_get_mcp_prompt_async(server_name, prompt_name, arguments or {}))
    except Exception as e:
        raise ValueError(f"Failed to get prompt '{prompt_name}' from server '{server_name}': {e}")


async def _get_mcp_prompt_async(
    server_name: str, prompt_name: str, arguments: Dict[str, Any]
) -> str:
    """Async implementation of prompt retrieval."""
    server_config = _server_configs[server_name]
    server_type = server_config.get("type", "local")

    if server_type == "local":
        return await _get_local_server_prompt(server_config, prompt_name, arguments)
    else:
        return await _get_remote_server_prompt(server_config, prompt_name, arguments)


async def _get_local_server_prompt(
    server_config: Dict[str, Any], prompt_name: str, arguments: Dict[str, Any]
) -> str:
    """Get prompt from a local MCP server."""
    command_parts = server_config.get("command", [])
    server_params = StdioServerParameters(
        command=command_parts[0],
        args=command_parts[1:] if len(command_parts) > 1 else [],
        env=server_config.get("environment", {}),
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.get_prompt(prompt_name, arguments=arguments)

            # Format the prompt messages into a readable string
            output_parts = []
            if hasattr(result, "messages"):
                for message in result.messages:
                    role = getattr(message, "role", "unknown")
                    content = message.content

                    # content is typically a list of content items
                    if isinstance(content, list):
                        for item in content:
                            if isinstance(item, TextContent):
                                output_parts.append(f"[{role}]: {item.text}")
                            elif hasattr(item, "text"):
                                output_parts.append(f"[{role}]: {item.text}")
                            else:
                                output_parts.append(f"[{role}]: {str(item)}")
                    elif isinstance(content, TextContent):
                        output_parts.append(f"[{role}]: {content.text}")
                    elif hasattr(content, "text"):
                        output_parts.append(f"[{role}]: {content.text}")
                    else:
                        output_parts.append(f"[{role}]: {str(content)}")
            else:
                # Fallback if structure is different
                output_parts.append(str(result))

    # Give subprocess time to clean up properly
    await asyncio.sleep(0.1)

    return "\n\n".join(output_parts) if output_parts else "Prompt executed successfully."


async def _get_remote_server_prompt(
    server_config: Dict[str, Any], prompt_name: str, arguments: Dict[str, Any]
) -> str:
    """Get prompt from a remote MCP server."""
    server_url = server_config.get("url", "")
    headers = server_config.get("headers", {})

    last_error = None

    # Try StreamableHTTP first
    try:
        async with streamablehttp_client(server_url, headers=headers) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.get_prompt(prompt_name, arguments=arguments)

                # Format the prompt messages into a readable string
                output_parts = []
                if hasattr(result, "messages"):
                    for message in result.messages:
                        role = getattr(message, "role", "unknown")
                        content = message.content

                        # content is typically a list of content items
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, TextContent):
                                    output_parts.append(f"[{role}]: {item.text}")
                                elif hasattr(item, "text"):
                                    output_parts.append(f"[{role}]: {item.text}")
                                else:
                                    output_parts.append(f"[{role}]: {str(item)}")
                        elif isinstance(content, TextContent):
                            output_parts.append(f"[{role}]: {content.text}")
                        elif hasattr(content, "text"):
                            output_parts.append(f"[{role}]: {content.text}")
                        else:
                            output_parts.append(f"[{role}]: {str(content)}")
                else:
                    # Fallback if structure is different
                    output_parts.append(str(result))

                return (
                    "\n\n".join(output_parts) if output_parts else "Prompt executed successfully."
                )
    except Exception as e:
        last_error = e
        # Continue to SSE fallback

    # Fallback to SSE
    try:
        async with sse_client(server_url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                result = await session.get_prompt(prompt_name, arguments=arguments)

                # Format the prompt messages into a readable string
                output_parts = []
                if hasattr(result, "messages"):
                    for message in result.messages:
                        role = getattr(message, "role", "unknown")
                        content = message.content

                        # content is typically a list of content items
                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, TextContent):
                                    output_parts.append(f"[{role}]: {item.text}")
                                elif hasattr(item, "text"):
                                    output_parts.append(f"[{role}]: {item.text}")
                                else:
                                    output_parts.append(f"[{role}]: {str(item)}")
                        elif isinstance(content, TextContent):
                            output_parts.append(f"[{role}]: {content.text}")
                        elif hasattr(content, "text"):
                            output_parts.append(f"[{role}]: {content.text}")
                        else:
                            output_parts.append(f"[{role}]: {str(content)}")
                else:
                    # Fallback if structure is different
                    output_parts.append(str(result))

                return (
                    "\n\n".join(output_parts) if output_parts else "Prompt executed successfully."
                )
    except Exception as sse_error:
        # Both transports failed
        if last_error:
            raise last_error
        raise sse_error


def _load_mcp_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load MCP configuration from file(s).

    If config_path is provided, loads only that file.

    Otherwise, merges configurations from both locations:
    1. ~/.patchpal/mcp-config.json (global config)
    2. .patchpal/mcp-config.json (project config - overrides global)

    Project-specific servers override global servers with the same name.
    This allows:
    - Global servers used across all projects
    - Project-specific servers or overrides
    - Disabling global servers per-project by setting "enabled": false

    Args:
        config_path: Optional explicit path to config file. If provided,
                    only that file is loaded (no merging).

    Returns:
        Merged configuration dict (empty if no config found)
    """
    if config_path is not None:
        # Explicit path provided - load only that file
        if config_path.exists():
            try:
                with open(
                    config_path, "r", encoding="utf-8", errors="surrogateescape", newline=None
                ) as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse MCP config at {config_path}: {e}")
                return {}
        return {}

    # Load and merge from both standard locations
    global_config_path = Path.home() / ".patchpal" / "mcp-config.json"
    project_config_path = Path(".patchpal") / "mcp-config.json"

    merged_config: Dict[str, Any] = {}

    # Load global config first
    if global_config_path.exists():
        try:
            with open(
                global_config_path, "r", encoding="utf-8", errors="surrogateescape", newline=None
            ) as f:
                global_config = json.load(f)
            merged_config = global_config
        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse global MCP config at {global_config_path}: {e}")

    # Load and merge project config (overrides global)
    if project_config_path.exists():
        try:
            with open(
                project_config_path, "r", encoding="utf-8", errors="surrogateescape", newline=None
            ) as f:
                project_config = json.load(f)

            # Merge MCP server configurations
            if "mcp" in project_config:
                if "mcp" not in merged_config:
                    merged_config["mcp"] = {}

                # Project servers override global servers by name
                merged_config["mcp"].update(project_config["mcp"])

            # Merge other top-level config keys (for future extensibility)
            for key, value in project_config.items():
                if key != "mcp":
                    merged_config[key] = value

        except json.JSONDecodeError as e:
            print(f"Warning: Failed to parse project MCP config at {project_config_path}: {e}")

    return merged_config


def is_mcp_available() -> bool:
    """Check if MCP SDK is available.

    Returns:
        True if MCP SDK is installed and can be imported
    """
    return MCP_AVAILABLE
