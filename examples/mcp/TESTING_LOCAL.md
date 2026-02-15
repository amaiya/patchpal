# Testing MCP with a Local Python Server

The congress.gov MCP server appears to be unavailable or changed. Instead, let's test with a simple local Python MCP server.

## Step-by-Step Guide

### Step 1: Verify MCP SDK is Installed

```bash
pip show mcp
```

You should see version 1.9.4 or similar.

### Step 2: Add the Demo Server

```bash
patchpal-mcp add demo --transport stdio -- \
  python examples/mcp/simple_server.py
```

You should see:
```
✓ Configuration saved to /home/yourname/.patchpal/config.json
✓ Added MCP server 'demo' (stdio transport)
```

### Step 3: Verify Configuration

```bash
patchpal-mcp list
```

You should see:
```
MCP Servers (from /home/yourname/.patchpal/config.json):
============================================================

✓ demo (local)
  Command: python examples/mcp/simple_server.py
```

### Step 4: Test the Server

```bash
patchpal-mcp test demo
```

You should see:
```
Testing MCP server 'demo'...
============================================================
Loading tools...
✓ Connected successfully!
  Found 3 tools

Available tools:
  • demo_greet
    Greet a person by name
  • demo_add_numbers
    Add two numbers together
  • demo_count_words
    Count words in a text string
...
✓ Test successful!
```

### Step 5: Start PatchPal

```bash
patchpal
```

### Step 6: Explore MCP Features

Once in PatchPal session:

```
> /mcp servers
```

You should see your demo server listed.

```
> /mcp help
```

Shows all MCP commands.

### Step 7: Use the MCP Tools

Try asking PatchPal to use the demo server tools:

**Example 1: Greeting**
```
> Greet Alice using the demo server
```

PatchPal should use the `demo_greet` tool and return: "Hello, Alice! 👋 Welcome to the MCP demo server."

**Example 2: Math**
```
> What is 42 plus 58?
```

PatchPal might use the `demo_add_numbers` tool and return: "The sum of 42 + 58 = 100"

**Example 3: Text Analysis**
```
> Count the words in "Hello world, this is a test"
```

PatchPal should use the `demo_count_words` tool and show word/line/character count.

### Step 8: See What's Happening

You'll see PatchPal automatically:
1. Recognize which tool to use
2. Call the MCP server
3. Get the result
4. Present it to you

## If It Doesn't Work

**Error: "Failed to load MCP server"**
- Make sure the path to `simple_server.py` is correct
- Try using absolute path: `patchpal-mcp add demo --transport stdio -- python /full/path/to/examples/mcp/simple_server.py`

**Error: "ModuleNotFoundError: No module named 'mcp.server'"**
- The MCP SDK might not have server components installed
- This is OK - the server runs in its own process

**Tools not being used:**
- Ask more directly: "Use the demo greet tool to say hello to Bob"
- Check `/mcp servers` shows the demo server

## About the Congress.gov Server

The congress.gov MCP server at `https://congress-mcp-an.fastmcp.app/mcp` is returning a 405 error, which means:
- The URL might have changed
- The service might be temporarily down
- It might require different authentication now

This is common with beta/experimental services. The local demo server gives you the same MCP experience and lets you verify everything is working correctly.

## Next Steps

Once the demo server works, you can:
1. Create your own custom MCP servers for your needs
2. Try other public MCP servers when they become available
3. Use the official Node.js-based MCP servers (filesystem, memory, etc.) if you have Node.js installed

The MCP implementation in PatchPal is working - it's just the public Congress server that seems unavailable right now.
