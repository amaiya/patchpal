# MCP (Model Context Protocol) for PatchPal

PatchPal supports the [Model Context Protocol (MCP)](https://modelcontextprotocol.io/), enabling AI assistants to connect to external data sources and tools through both local and remote MCP servers.

## Quick Start

### 1. Install MCP Support

```bash
pip install patchpal[mcp]
```

### 2. Add an MCP Server

**Using the CLI (recommended):**

```bash
# Add a remote HTTP server (Hugging Face)
patchpal-mcp add huggingface https://huggingface.co/mcp \
  --header "Authorization: Bearer ${HF_TOKEN}"

# Add a local stdio server
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /path/to/dir

# List all configured servers
patchpal-mcp list

# Test a server connection
patchpal-mcp test huggingface
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

MCP tools will be automatically loaded and prefixed with the server name (e.g., `hf_model_search`).

### 4. Explore MCP Features in Session

Once in a PatchPal session, use `/mcp` commands:

```
> /mcp servers           # List configured servers
> /mcp tools             # List all loaded MCP tools
> /mcp tools huggingface # List tools from specific server
> /mcp resources         # List available resources
> /mcp prompts           # List available prompts
> /mcp help              # Show MCP command help
```

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
        "Authorization": "Bearer ${API_TOKEN}"
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

## Example: Hugging Face Server

Access the Hugging Face Hub - search models, datasets, Spaces, papers, and documentation.

**Setup:**

1. Get your API token from https://huggingface.co/settings/tokens
2. Set environment variable:
   ```bash
   export HF_TOKEN="hf_your_token_here"
   ```
3. Add to config:
   ```bash
   patchpal-mcp add huggingface https://huggingface.co/mcp \
     --header "Authorization: Bearer ${HF_TOKEN}"
   ```

**Available Tools:**
- `hf_model_search` - Search for ML models
- `hf_dataset_search` - Find datasets
- `hf_space_search` - Discover AI apps/demos
- `hf_paper_search` - Search ML research papers
- `hf_doc_search` - Search Hugging Face documentation

**Example Queries:**
- "Find quantized versions of Qwen 3"
- "Search for datasets about weather time-series"
- "What are the most popular text-to-image models?"

## Finding More Servers

- [MCP Server Registry](https://mcp.so) - Searchable directory
- [GitHub Official Servers](https://github.com/modelcontextprotocol/servers) - Reference implementations
- [FastMCP Cloud](https://fastmcp.wiki/) - Host your own servers

## Managing MCP Servers with CLI

### Add a Server

```bash
# Add remote HTTP server
patchpal-mcp add <name> <url> [options]

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
```

### Test Server Connection

```bash
patchpal-mcp test <name>
```

### Remove a Server

```bash
patchpal-mcp remove <name>
```

## MCP Resources and Prompts

In addition to tools, MCP servers can expose **resources** (data/documents) and **prompts** (pre-defined prompt templates).

### Demo Script

Run the demo to see resources and prompts from your configured servers:

```bash
python examples/mcp/demo_resources_prompts.py
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

See `simple_server.py` in this directory for a complete example.

## Authentication

Most MCP servers that require authentication accept **personal access tokens** or **API keys**.

### Recommended Workflow

**Step 1: Get a personal access token**

Visit the service's settings page (e.g., "API Keys", "Access Tokens", or "Developer Settings").

**Step 2: Store token as environment variable**

```bash
# Add to your ~/.bashrc, ~/.zshrc, or equivalent
export HF_TOKEN="hf_xxxxxxxxxxxxxxxxxxxx"

# Reload your shell
source ~/.bashrc
```

**Step 3: Configure PatchPal to use the token**

```bash
patchpal-mcp add huggingface https://huggingface.co/mcp \
  --header "Authorization: Bearer ${HF_TOKEN}"
```

Your config file will contain the variable reference, not the actual token:

```json
{
  "huggingface": {
    "type": "remote",
    "url": "https://huggingface.co/mcp",
    "enabled": true,
    "headers": {
      "Authorization": "Bearer ${HF_TOKEN}"
    }
  }
}
```

### Benefits

- ✅ **Secure** - Tokens never stored in config files
- ✅ **Simple** - No browser popups or OAuth flows needed
- ✅ **Portable** - Works in SSH sessions, containers, CI/CD

## Troubleshooting

### MCP Tools Not Loading

```bash
# Check MCP SDK installation
pip install patchpal[mcp]
python -c "import mcp; print('OK')"

# Validate configuration
cat ~/.patchpal/config.json | python -m json.tool
```

### Environment Variable Not Found

Set the environment variable or use a default value:
```json
"url": "${API_URL:-https://default.example.com}"
```

### Remote Server Connection Failed

```bash
# Test server accessibility
curl -I https://huggingface.co/mcp
```

## Resources

- [Model Context Protocol Specification](https://modelcontextprotocol.io/)
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [MCP Server Registry](https://mcp.so)
- [PatchPal Documentation](../../README.md)
