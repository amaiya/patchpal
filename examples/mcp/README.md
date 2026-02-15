# MCP (Model Context Protocol) for PatchPal

PatchPal supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling AI assistants to connect to external data sources and tools through both local and remote MCP servers.

## Quick Start

### 1. Install MCP Support

```bash
pip install patchpal[mcp]
```

### 2. Create Configuration

Create `~/.patchpal/config.json` (or `.patchpal/config.json` for project-specific config):

```bash
mkdir -p ~/.patchpal
cp examples/mcp/config.example.json ~/.patchpal/config.json
```

Edit the file to enable servers. See [Configuration](#configuration) for details.

### 3. Start PatchPal

```bash
patchpal
```

MCP tools will be automatically loaded and prefixed with the server name (e.g., `congress_search_bills`).

## Configuration

PatchPal supports two types of MCP servers:

### Local Servers (stdio transport)

Run as processes on your machine:

```json
{
  "mcp": {
    "filesystem": {
      "type": "local",
      "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"],
      "enabled": true,
      "environment": {}
    }
  }
}
```

### Remote Servers (HTTP/SSE transport)

Connect to hosted MCP services:

```json
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
```

## Popular MCP Servers

### Congress.gov (Remote)

Access U.S. legislative data - bills, members, committees, hearings, and votes.

**Configuration:**
```json
{
  "congress": {
    "type": "remote",
    "url": "https://congress-mcp-an.fastmcp.app/mcp",
    "enabled": true
  }
}
```

**Example Queries:**
- "What bills about AI were introduced in the 119th Congress?"
- "Show me the latest actions on bill H.R. 3076"
- "Who are the sponsors of recent healthcare legislation?"

### Official MCP Servers (Local)

The MCP project maintains reference implementations:

**Filesystem** - Secure file operations with access controls
```json
{
  "filesystem": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-filesystem", "/allowed/path"],
    "enabled": true
  }
}
```

**Memory** - Knowledge graph-based persistent memory
```json
{
  "memory": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-memory"],
    "enabled": true
  }
}
```

**Fetch** - Web content fetching and conversion
```json
{
  "fetch": {
    "type": "local",
    "command": ["npx", "-y", "@modelcontextprotocol/server-fetch"],
    "enabled": true
  }
}
```

### Finding More Servers

- [MCP Server Registry](https://mcp.so) - Searchable directory
- [GitHub Official Servers](https://github.com/modelcontextprotocol/servers) - Reference implementations
- [FastMCP Cloud](https://fastmcp.wiki/) - Host your own servers

## Testing Your Setup

### Test Remote Server Connection

Verify you can connect to a remote MCP server:

```bash
python examples/mcp/test_remote_mcp.py
```

Expected output:
```
Connecting to https://congress-mcp-an.fastmcp.app/mcp...
✓ Connected successfully!

Available tools (X):
  • search_bills
  • get_bill_details
  ...

✓ Test successful!
```

### Validate Configuration

```bash
# Check config is valid JSON
cat ~/.patchpal/config.json | python -m json.tool

# Verify MCP SDK is installed
python -c "from mcp.client.sse import sse_client; print('MCP available')"
```

## Creating Custom MCP Servers

Build your own MCP server with the Python SDK:

```python
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("My Server")

@mcp.tool()
def my_tool(argument: str) -> str:
    """What this tool does."""
    return f"Processed: {argument}"

if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Save as `my_server.py` and configure:

```json
{
  "custom": {
    "type": "local",
    "command": ["python", "/path/to/my_server.py"],
    "enabled": true
  }
}
```

See `simple_server.py` in this directory for a complete example.

## Troubleshooting

### MCP Tools Not Loading

**Check MCP SDK installation:**
```bash
pip install patchpal[mcp]
python -c "import mcp; print('OK')"
```

**Validate configuration:**
```bash
cat ~/.patchpal/config.json | python -m json.tool
```

**Check PatchPal logs** for MCP-related warnings when starting.

### Local Server Won't Start

**Test the server command directly:**
```bash
npx -y @modelcontextprotocol/server-filesystem /tmp
```

**Check if the package is installed:**
```bash
pip list | grep mcp
npm list -g | grep mcp
```

**Verify environment variables** are set correctly in your config.

### Remote Server Connection Failed

**Test server accessibility:**
```bash
curl -I https://congress-mcp-an.fastmcp.app/mcp
```

**Common issues:**
- Network/firewall blocking HTTPS connections
- Missing or incorrect authentication headers
- Server is temporarily unavailable

**Check PatchPal output** for specific error messages.

### Tools Exist But Don't Work

- Verify you're using the correct tool parameters
- Check PatchPal's output for error messages from the MCP server
- Some tools have required parameters - see tool descriptions

## Architecture

```
PatchPal Agent
     │
     ├─── Built-in Tools (file ops, git, web, etc.)
     │
     └─── MCP Tools
          │
          ├─── Local Servers (stdio)
          │    └─── Filesystem, Memory, Custom
          │
          └─── Remote Servers (HTTP/SSE)
               └─── Congress.gov, Hosted Services
```

## Authentication

Remote servers support custom HTTP headers:

```json
{
  "authenticated_service": {
    "type": "remote",
    "url": "https://api.example.com/mcp",
    "enabled": true,
    "headers": {
      "Authorization": "Bearer YOUR_API_TOKEN",
      "X-API-Key": "your-key",
      "X-Custom-Header": "custom-value"
    }
  }
}
```

## Limitations

Current limitations (may be addressed in future updates):

- **Connection per call** - Each tool invocation creates a new connection (no connection pooling yet)
- **Static auth only** - OAuth flows not supported, only static headers
- **SSE transport only** - WebSocket not supported for remote servers

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Server Registry](https://mcp.so)
- [FastMCP Documentation](https://fastmcp.wiki/)
- [PatchPal Documentation](../../README.md)
