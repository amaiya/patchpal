# MCP (Model Context Protocol) for PatchPal

PatchPal supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling AI assistants to connect to external data sources and tools through both local and remote MCP servers.

## Quick Start

### 1. Install MCP Support

```bash
pip install patchpal[mcp]
```

### 2. Add an MCP Server

You can add MCP servers using the CLI or by editing the config file manually.

**Using the CLI (recommended):**

```bash
# Add a remote HTTP server (congress.gov)
patchpal-mcp add congress https://congress-mcp-an.fastmcp.app/mcp

# Add with authentication
patchpal-mcp add github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer ${GITHUB_TOKEN}"

# Add a local stdio server
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /path/to/dir

# List all configured servers
patchpal-mcp list

# Test a server connection
patchpal-mcp test congress
```

**Manual configuration:**

Create `~/.patchpal/config.json`:

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

### Environment Variable Expansion

Keep sensitive credentials out of config files using environment variables:

```json
{
  "mcp": {
    "api_server": {
      "type": "remote",
      "url": "${API_BASE_URL:-https://api.example.com/mcp}",
      "enabled": true,
      "headers": {
        "Authorization": "Bearer ${API_TOKEN}",
        "X-API-Key": "${API_KEY}"
      }
    },
    "database": {
      "type": "local",
      "command": ["npx", "-y", "@bytebase/dbhub"],
      "enabled": true,
      "environment": {
        "DB_HOST": "${DATABASE_HOST:-localhost}",
        "DB_PASSWORD": "${DATABASE_PASSWORD}"
      }
    }
  }
}
```

**Syntax:**
- `${VAR}` - Expands to the value of environment variable `VAR` (fails if not set)
- `${VAR:-default}` - Uses `VAR` if set, otherwise uses `default` value

**Example:**
```bash
# Set environment variables
export API_TOKEN="your-secret-token"
export DATABASE_PASSWORD="db-password"

# Start PatchPal - variables will be expanded automatically
patchpal
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

**With optional authentication (if required in the future):**
```json
{
  "congress": {
    "type": "remote",
    "url": "${CONGRESS_API_URL:-https://congress-mcp-an.fastmcp.app/mcp}",
    "enabled": true,
    "headers": {
      "Authorization": "Bearer ${CONGRESS_API_KEY}"
    }
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

## Managing MCP Servers with CLI

PatchPal provides a convenient CLI for managing MCP servers.

### Add a Server

```bash
# Add remote HTTP server
patchpal-mcp add <name> <url> [options]

# Examples:
patchpal-mcp add congress https://congress-mcp-an.fastmcp.app/mcp
patchpal-mcp add github https://api.githubcopilot.com/mcp/

# With authentication headers
patchpal-mcp add sentry https://mcp.sentry.dev/mcp \
  --header "Authorization: Bearer ${SENTRY_TOKEN}"

# Add local stdio server
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /path/to/dir

# With environment variables
patchpal-mcp add db --transport stdio \
  --env DB_HOST=localhost \
  --env DB_PASSWORD=${DB_PASS} -- \
  npx -y @bytebase/dbhub

# Add to project config (shared via git)
patchpal-mcp add myserver https://api.example.com/mcp --scope project
```

### List Servers

```bash
patchpal-mcp list

# Output:
# MCP Servers (from /home/user/.patchpal/config.json):
# ============================================================
#
# ✓ congress (remote)
#   URL: https://congress-mcp-an.fastmcp.app/mcp
#
# ✓ filesystem (local)
#   Command: npx -y @modelcontextprotocol/server-filesystem /path/to/dir
```

### Get Server Details

```bash
patchpal-mcp get <name>

# Example:
patchpal-mcp get congress
```

### Test Server Connection

```bash
patchpal-mcp test <name>

# Example:
patchpal-mcp test congress
# Testing MCP server 'congress'...
# ============================================================
# Loading tools...
# ✓ Connected successfully!
#   Found 15 tools
#
# Available tools:
#   • congress_search_bills
#   • congress_get_bill
#   ...
```

### Remove a Server

```bash
patchpal-mcp remove <name>

# Example:
patchpal-mcp remove congress
```

### Configuration Scopes

- `--scope user` (default): `~/.patchpal/config.json` - Personal config
- `--scope project`: `.patchpal/config.json` - Project-specific, shared via git
- `--scope local`: Same as `project`

## MCP Resources and Prompts

In addition to tools, MCP servers can expose **resources** (data/documents) and **prompts** (pre-defined prompt templates).

### Listing Resources

```python
from patchpal.tools.mcp import load_mcp_tools, list_mcp_resources, read_mcp_resource

# Load tools first (initializes servers)
load_mcp_tools()

# List all available resources
resources = list_mcp_resources()
for resource in resources:
    print(f"{resource['server']}: {resource['uri']}")

# Read a specific resource
content = read_mcp_resource(server_name="github", uri="repo://issues/123")
```

### Listing Prompts

```python
from patchpal.tools.mcp import load_mcp_tools, list_mcp_prompts

# Load tools first (initializes servers)
load_mcp_tools()

# List all available prompts
prompts = list_mcp_prompts()
for prompt in prompts:
    print(f"{prompt['server']}/{prompt['name']}: {prompt['description']}")
    for arg in prompt.get('arguments', []):
        print(f"  - {arg['name']} ({'required' if arg['required'] else 'optional'})")
```

### Demo Script

Run the demo to see resources and prompts from your configured servers:

```bash
python examples/mcp/demo_resources_prompts.py
```

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

### Environment Variable Not Found

If you see an error like `Environment variable 'API_TOKEN' is not set`, either:

1. **Set the environment variable:**
   ```bash
   export API_TOKEN="your-token"
   patchpal
   ```

2. **Use a default value in config:**
   ```json
   "url": "${API_URL:-https://default.example.com}"
   ```

3. **Remove the variable reference** and use the actual value (less secure for tokens)

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

Most MCP servers that require authentication accept **personal access tokens** or **API keys** which you can obtain from the service's settings/developer portal.

### Recommended Workflow

**Step 1: Get a personal access token**

Visit the service's settings page:
- **GitHub**: Settings → Developer settings → Personal access tokens
- **Sentry**: Settings → Auth Tokens → Create New Token
- **Other services**: Look for "API Keys", "Access Tokens", or "Developer Settings"

**Step 2: Store token as environment variable**

```bash
# Add to your ~/.bashrc, ~/.zshrc, or equivalent
export GITHUB_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export SENTRY_TOKEN="sntrys_xxxxxxxxxxxxxxxxxx"

# Reload your shell or run:
source ~/.bashrc
```

**Step 3: Configure PatchPal to use the token**

```bash
# The ${GITHUB_TOKEN} will be expanded from your environment
patchpal-mcp add github https://api.githubcopilot.com/mcp/ \
  --header "Authorization: Bearer ${GITHUB_TOKEN}"

patchpal-mcp add sentry https://mcp.sentry.dev/mcp \
  --header "Authorization: Bearer ${SENTRY_TOKEN}"
```

**Step 4: Start using PatchPal**

```bash
patchpal
# Tokens are loaded from environment automatically
```

### Configuration Example

Your config file will contain the variable reference, not the actual token:

```json
{
  "github": {
    "type": "remote",
    "url": "https://api.githubcopilot.com/mcp/",
    "enabled": true,
    "headers": {
      "Authorization": "Bearer ${GITHUB_TOKEN}"
    }
  }
}
```

The actual token value stays secure in your environment variables.

### Benefits of This Approach

- ✅ **Secure** - Tokens never stored in config files or version control
- ✅ **Simple** - No browser popups or OAuth flows needed
- ✅ **Portable** - Works in SSH sessions, containers, CI/CD
- ✅ **Long-lived** - Personal tokens typically don't expire or expire rarely
- ✅ **Easy rotation** - Just update the environment variable

### Alternative: Inline Headers (Less Secure)

For non-sensitive or temporary testing:

```json
{
  "headers": {
    "Authorization": "Bearer your-actual-token-here"
  }
}
```

⚠️ **Warning**: Don't commit actual tokens to git!

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
