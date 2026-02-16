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
> /mcp servers        # List configured servers
> /mcp tools          # Show all MCP tools
> /mcp resources      # List resources (view only)
> /mcp prompts        # List prompts (view only)
> /mcp help           # Show MCP commands
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

### Official @modelcontextprotocol Servers

The MCP steering group maintains official reference servers available via npm:

- **@modelcontextprotocol/server-filesystem** - Secure file operations with configurable access controls
- **@modelcontextprotocol/server-git** - Git repository management and operations
- **@modelcontextprotocol/server-everything** - Reference/test server demonstrating all MCP features
- **@modelcontextprotocol/server-fetch** - Web content fetching and conversion
- **@modelcontextprotocol/server-memory** - Knowledge graph-based persistent memory
- **@modelcontextprotocol/server-sequential-thinking** - Dynamic problem-solving through thought sequences
- **@modelcontextprotocol/server-time** - Time and timezone conversion capabilities

Browse all official packages: https://www.npmjs.com/org/modelcontextprotocol

**Usage:**
```bash
# View available servers
npm search @modelcontextprotocol

# Add to PatchPal (npx -y auto-installs if needed)
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /allowed/path
```

### Community Servers

- **[MCP Server Registry](https://mcp.so)** - Searchable directory of 500+ servers
- **[GitHub Official Servers](https://github.com/modelcontextprotocol/servers)** - Reference implementations & archived servers
- **[FastMCP Cloud](https://fastmcp.wiki/)** - Host your own servers

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
/mcp servers                # List configured servers
/mcp tools                  # List all loaded MCP tools
/mcp tools [server]         # List tools from specific server
/mcp resources              # List available resources (view only)
/mcp resources [server]     # List resources from specific server
/mcp prompts                # List available prompts (view only)
/mcp prompts [server]       # List prompts from specific server
/mcp help                   # Show all MCP commands
```

**Note:** Resources and prompts are displayed for reference but are not automatically exposed as agent tools. MCP tools are the primary way for agents to interact with MCP servers.

## Examples

### Hugging Face Hub

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

### Filesystem Access

Secure file operations with path restrictions:

```bash
patchpal-mcp add filesystem --transport stdio -- \
  npx -y @modelcontextprotocol/server-filesystem /home/user/projects

# Agent can now access files in /home/user/projects
```

## MCP Resources and Prompts

In addition to tools, MCP servers can expose:

- **Resources** - Data and documents that servers make available (e.g., configuration files, documentation, database schemas)
- **Prompts** - Pre-defined prompt templates with arguments for common tasks

These are available for **viewing and reference** via `/mcp resources` and `/mcp prompts` commands in a PatchPal session, but are not automatically exposed as agent tools. This allows you to discover what a server provides without cluttering the agent's tool list.

**Use Cases:**
- **Resources**: View what data sources are available before deciding how to access them
- **Prompts**: See pre-built templates that demonstrate common workflows with the server

**Demo:**

See resources and prompts in action:

```bash
python examples/mcp/demo_resources_prompts.py
```

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
cat ~/.patchpal/mcp-config.json | python -m json.tool
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

# Test with patchpal-mcp
patchpal-mcp test huggingface
```

### Local Server Won't Start

```bash
# Verify command works standalone
npx -y @modelcontextprotocol/server-filesystem /tmp

# Check logs when starting PatchPal
patchpal  # Look for error messages about MCP server initialization
```

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
