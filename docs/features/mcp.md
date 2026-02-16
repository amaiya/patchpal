# MCP (Model Context Protocol)

PatchPal supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling AI assistants to connect to external data sources and tools through both local and remote MCP servers.

## Quick Start

### 1. Install MCP Support

```bash
pip install patchpal[mcp]
```

### 2. Add an MCP Server

**Using the CLI (recommended):**

```bash
# Add a remote server
patchpal-mcp add huggingface https://huggingface.co/mcp \
  --header "Authorization: Bearer ${HF_TOKEN}"

# Add a local server
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /path/to/dir

# List configured servers
patchpal-mcp list

# Test a server connection
patchpal-mcp test huggingface
```

### 3. Use in PatchPal

```bash
patchpal

# In session - use MCP commands
> /mcp servers    # List configured servers
> /mcp tools      # Show all MCP tools
> /mcp help       # Show MCP commands
```

MCP tools are automatically loaded and available to the agent (e.g., `filesystem_read_file`, `hf_model_search`).

## Configuration

MCP servers are configured in JSON files. PatchPal merges configurations from:
- **Global**: `~/.patchpal/mcp-config.json` (used across all projects)
- **Project**: `.patchpal/mcp-config.json` (project-specific, overrides global)

### Local Servers (stdio)

Run as processes on your machine:

```json
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"],
      "enabled": true
    }
  }
}
```

### Remote Servers (HTTP/SSE)

Connect to hosted MCP services:

```json
{
  "mcp": {
    "huggingface": {
      "type": "remote",
      "url": "https://huggingface.co/mcp",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer ${HF_TOKEN}"
      }
    }
  }
}
```

### Environment Variables

Keep credentials secure using environment variable expansion:

```json
{
  "mcp": {
    "api": {
      "type": "remote",
      "url": "${API_URL:-https://api.example.com}",
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}"
      }
    }
  }
}
```

**Syntax:**
- `${VAR}` - Required variable (fails if not set)
- `${VAR:-default}` - Optional with default value

## Config Merging

Project configs override global configs by server name:

```json
// Global: ~/.patchpal/mcp-config.json
{"mcp": {"api": {"url": "https://dev.example.com"}}}

// Project: .patchpal/mcp-config.json
{"mcp": {"api": {"url": "https://prod.example.com"}}}

// Result: Project uses prod URL
```

Disable a global server for specific projects:

```json
// Project: .patchpal/mcp-config.json
{"mcp": {"filesystem": {"enabled": false}}}
```

## Finding MCP Servers

- **[MCP Server Registry](https://mcp.so)** - 500+ community servers
- **[Official Servers](https://www.npmjs.com/org/modelcontextprotocol)** - Reference implementations
  - `@modelcontextprotocol/server-filesystem` - File operations
  - `@modelcontextprotocol/server-git` - Git operations
  - `@modelcontextprotocol/server-memory` - Knowledge graph
  - And more...
- **[FastMCP Cloud](https://fastmcp.wiki/)** - Host your own

## Managing Servers

```bash
# Add server
patchpal-mcp add <name> <url> [options]

# List all servers
patchpal-mcp list

# Get server details
patchpal-mcp get <name>

# Test connection
patchpal-mcp test <name>

# Remove server
patchpal-mcp remove <name>

# Scope (--scope flag)
#   user    : ~/.patchpal/mcp-config.json (default, all projects)
#   project : .patchpal/mcp-config.json (current project only)
```

## In-Session Commands

Once in a PatchPal session:

```bash
/mcp servers              # List configured servers
/mcp tools                # List all loaded MCP tools
/mcp tools <server>       # List tools from specific server
/mcp resources            # List available resources
/mcp prompts              # List available prompts
/mcp help                 # Show all MCP commands
```

## Examples

### Hugging Face Hub

Access ML models, datasets, and documentation:

```bash
# Setup
export HF_TOKEN="hf_your_token"
patchpal-mcp add huggingface https://huggingface.co/mcp \
  --header "Authorization: Bearer ${HF_TOKEN}"

# Use in session
patchpal
> Find quantized versions of Llama 3
> Search for weather time-series datasets
```

### Filesystem Access

Secure file operations with path restrictions:

```bash
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /home/user/projects

# Agent can now access files in /home/user/projects
```

## Creating Custom Servers

Build your own MCP server with Python:

```python
from mcp.server import Server

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [...]  # Define tools

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # Handle tool execution
    return [TextContent(type="text", text=result)]

# Run with stdio transport
server.run(transport="stdio")
```

See `examples/mcp/simple_server.py` for a complete example.

## Resources

- **[MCP Specification](https://modelcontextprotocol.io/)** - Official protocol docs
- **[Example Servers](../examples/mcp/)** - Local examples and testing guides
- **[MCP CLI Reference](../examples/mcp/README.md)** - Detailed CLI documentation
- **[Python SDK](https://github.com/modelcontextprotocol/python-sdk)** - Build custom servers
