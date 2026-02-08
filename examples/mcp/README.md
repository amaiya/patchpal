# MCP (Model Context Protocol) Examples for PatchPal

This directory contains example configurations and documentation for integrating MCP servers with PatchPal.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard that enables AI applications to securely connect to external data sources and tools. MCP servers provide tools, resources, and prompts that can be used by AI assistants.

## Quick Start

### 1. Install PatchPal with MCP Support

```bash
pip install patchpal[mcp]
```

### 2. Create Configuration File

Create a configuration file in one of these locations:
- `~/.patchpal/config.json` (personal configuration)
- `.patchpal/config.json` (project-specific configuration)

Use the example configuration as a template:

```bash
mkdir -p ~/.patchpal
cp examples/mcp/config.example.json ~/.patchpal/config.json
```

### 3. Configure MCP Servers

Edit the configuration file to enable and configure MCP servers. Each server needs:
- `type`: Currently only `"local"` is supported (stdio transport)
- `command`: Array with command and arguments to start the server
- `enabled`: Set to `true` to enable the server
- `environment`: Optional environment variables

Example:

```json
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["python", "-m", "mcp_server_filesystem", "/home/user/documents"],
      "enabled": true,
      "environment": {}
    }
  }
}
```

### 4. Run PatchPal

PatchPal will automatically discover and load tools from configured MCP servers:

```bash
patchpal
```

MCP tools will be available alongside built-in PatchPal tools, prefixed with the server name (e.g., `filesystem_read_file`).

## Available MCP Servers

Here are some popular MCP servers you can use with PatchPal:

### Official Reference Servers

The Model Context Protocol project provides several reference servers maintained by the steering group:

#### Filesystem Server

Secure file operations with configurable access controls.

```bash
# Uses npx to run the official server
npx -y @modelcontextprotocol/server-filesystem
```

Configuration:
```json
{
  "filesystem": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"],
    "enabled": true
  }
}
```

#### Memory Server

Knowledge graph-based persistent memory system.

```bash
npx -y @modelcontextprotocol/server-memory
```

Configuration:
```json
{
  "memory": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
    "enabled": true
  }
}
```

#### Fetch Server

Web content fetching and conversion for efficient LLM usage.

```bash
npx -y @modelcontextprotocol/server-fetch
```

Configuration:
```json
{
  "fetch": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
    "enabled": true
  }
}
```

### Community MCP Servers

Thousands of community-built MCP servers are available. Browse them at:
- [Official MCP Registry](https://mcp.so)
- [GitHub modelcontextprotocol/servers](https://github.com/modelcontextprotocol/servers)

Many are available as npm packages using `npx` (no installation required).

## Creating Custom MCP Servers

You can create custom MCP servers using the Python MCP SDK. Here's a minimal example:

```python
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("My Custom Server")

@mcp.tool()
def my_custom_tool(argument: str) -> str:
    """Description of what this tool does."""
    return f"Processed: {argument}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Save this as `my_server.py` and configure it in PatchPal:

```json
{
  "custom": {
    "type": "local",
    "command": ["python", "/path/to/my_server.py"],
    "enabled": true
  }
}
```

## Architecture

```
┌─────────────┐
│  PatchPal   │
│   Agent     │
└──────┬──────┘
       │
       │ Tool Calls
       │
┌──────▼───────────────────────────┐
│  Tool Registry                   │
│  ┌────────────┐  ┌────────────┐ │
│  │  Built-in  │  │    MCP     │ │
│  │   Tools    │  │   Tools    │ │
│  └────────────┘  └──────┬─────┘ │
└────────────────────────┬─────────┘
                         │
                         │ stdio/JSON-RPC
                         │
              ┌──────────▼──────────┐
              │   MCP Server(s)     │
              │  ┌───────────────┐  │
              │  │  Filesystem   │  │
              │  │  PostgreSQL   │  │
              │  │    SQLite     │  │
              │  │     Git       │  │
              │  │    Custom     │  │
              │  └───────────────┘  │
              └─────────────────────┘
```

## Current Limitations

- **Local servers only**: Remote MCP servers (HTTP/SSE) are not yet supported
- **No OAuth**: Authentication for remote servers not implemented
- **Connection per call**: Each tool call creates a new connection (will be optimized later)
- **stdio transport only**: Only local process communication supported

These limitations will be addressed in future updates.

## Troubleshooting

### MCP tools not loading

1. Check that PatchPal was installed with MCP support:
   ```bash
   python -c "import mcp; print('MCP available')"
   ```
   
   If not installed, run:
   ```bash
   pip install patchpal[mcp]
   ```

2. Verify your configuration file exists and is valid JSON:
   ```bash
   cat ~/.patchpal/config.json | python -m json.tool
   ```

3. Check PatchPal logs for MCP-related warnings

### MCP server fails to start

1. Test the MCP server command manually:
   ```bash
   python -m mcp_server_filesystem /tmp
   ```

2. Check environment variables are set correctly

3. Verify the server package is installed:
   ```bash
   pip list | grep mcp
   ```

## Resources

- [Model Context Protocol Documentation](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [Official MCP Servers](https://github.com/modelcontextprotocol/servers)
- [PatchPal Documentation](../../README.md)

## Examples

See the `config.example.json` file in this directory for a complete configuration example with multiple MCP servers.
