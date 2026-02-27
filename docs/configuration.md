# Configuration

PatchPal can be configured through `PATCHPAL_*` environment variables to customize behavior, security, and performance.

### Model Selection

```bash
export PATCHPAL_MODEL=openai/gpt-5.2          # Override default model
# Priority: CLI arg > PATCHPAL_MODEL env var > default (anthropic/claude-sonnet-4-5)

# Extra LiteLLM parameters (JSON format)
export PATCHPAL_LITELLM_KWARGS='{"reasoning_effort": "high", "temperature": 0.7}'
# Use for: reasoning models (gpt-oss, deepseek-reasoner), temperature, max_tokens, etc.
# See: https://docs.litellm.ai/docs/completion/input
```

### Security & Permissions

#### Maximum Security Mode

For environments requiring the highest level of security, use the `--maximum-security` CLI flag:

```bash
patchpal --maximum-security
```

This single flag enables **all** security restrictions:
- **Permission for all operations**: Requires approval for ALL operations including read operations (`read_file`, `list_files`, etc.)
- **Repository-only access**: Blocks reading/writing files outside the repository directory (`PATCHPAL_RESTRICT_TO_REPO=true`)
- **Web access disabled**: Disables web search and fetch tools to prevent data spillage (`PATCHPAL_ENABLE_WEB=false`)

**When to use:**
- Processing sensitive codebases with PII or confidential data
- Working in compliance-driven environments (HIPAA, SOC2, etc.)
- Evaluating untrusted prompts or skills

**Granular Control:**

You can also enable these restrictions individually:

```bash
# Require permission for all operations (including reads)
patchpal --require-permission-for-all

# Or use environment variables for fine-grained control
export PATCHPAL_RESTRICT_TO_REPO=true  # Block access outside repository
export PATCHPAL_ENABLE_WEB=false       # Disable web access
patchpal
```

#### Environment Variables

```bash
# Permission System
export PATCHPAL_REQUIRE_PERMISSION=true      # Prompt before executing commands/modifying files (default: true)
                                              # ⚠️  WARNING: Setting to false disables prompts - only use in trusted environments

# File Safety
export PATCHPAL_MAX_FILE_SIZE=512000         # Maximum file size in bytes for read/write (default: 500KB)
                                             # Applies to: text files, SVG files
                                             # Reduced from 10MB to prevent context window explosions
export PATCHPAL_MAX_IMAGE_SIZE=10485760      # Maximum image file size in bytes (default: 10MB)
                                             # Applies to: PNG, JPG, GIF, BMP, WEBP (not SVG)
                                             # Images are formatted as multimodal content, bypassing tool output limits
                                             # Vision APIs resize images automatically, so 1-2MB is optimal
export PATCHPAL_MAX_TOOL_OUTPUT_LINES=2000   # Maximum lines per tool output (default: 2000)
                                             # Prevents any single tool from dominating context
export PATCHPAL_MAX_TOOL_OUTPUT_CHARS=100000 # Maximum characters per tool output (default: 100K)
                                             # Applied after tool execution to all tool results
                                             # Character-based (not bytes) to avoid breaking Unicode
export PATCHPAL_READ_ONLY=true               # Prevent ALL file modifications (default: false)
                                             # Useful for: code review, exploration, security audits
export PATCHPAL_ALLOW_SENSITIVE=true         # Allow access to .env, credentials (default: false - blocked)
                                             # Only enable with test/dummy credentials
export PATCHPAL_RESTRICT_TO_REPO=true        # Restrict file access to repository only (default: false)
                                             # Prevents reading/writing files outside the repository directory
                                             # Useful for: preventing PII leakage from external files
                                             # Examples of blocked paths: /tmp/file.txt, ~/Documents/notes.txt, ../../etc/passwd

# Command Safety
export PATCHPAL_ALLOW_SUDO=true              # Allow sudo/privilege escalation (default: false - blocked)
                                              # ⚠️  WARNING: Only enable in trusted, controlled environments
export PATCHPAL_SHELL_TIMEOUT=60             # Shell command timeout in seconds (default: 30)

# Output Filtering
export PATCHPAL_FILTER_OUTPUTS=true          # Filter verbose command outputs (default: true)
                                              # Only applies to specific commands: test runners, git log, build tools
                                              # Patterns matched: pytest, npm test, git log, pip install, cargo build, etc.
                                              # Shows only failures, errors, and summaries for matched commands
                                              # Can save 75%+ on output tokens for verbose commands
                                              # All other commands return full output
export PATCHPAL_MAX_OUTPUT_LINES=500         # Max lines of shell output (default: 500)
                                              # Applied to ALL shell commands to prevent context flooding
                                              # If output exceeds this, shows first/last portions with truncation notice
```

### Operational Controls

```bash
# Logging & Auditing
export PATCHPAL_AUDIT_LOG=false              # Log operations to ~/.patchpal/repos/<repo-name>/audit.log (default: true)
export PATCHPAL_ENABLE_BACKUPS=true          # Auto-backup files before modification (default: false)

# Resource Limits
export PATCHPAL_MAX_OPERATIONS=10000         # Max operations per session (default: 10000)
export PATCHPAL_MAX_ITERATIONS=150           # Max agent iterations per task (default: 100)
                                              # Increase for complex multi-file tasks
export PATCHPAL_LLM_TIMEOUT=300              # LLM API timeout in seconds (default: 300 = 5 minutes)
                                              # Overall request timeout for long-running operations
                                              # Works with automatic retry logic for network resilience
```

### Network Resilience

PatchPal includes automatic retry logic to handle unstable network connections. This prevents hangs when running on corporate networks with intermittent connectivity.

**How it works:**
- **Socket-level timeouts**: Detect stale connections quickly (10s connect, 60s read, 30s write)
- **Automatic retries**: Up to 3 attempts with exponential backoff (1s, 2s, 4s)
- **Smart error handling**: Retries network errors (timeouts, 502/503/504), fails immediately on auth/validation errors
- **Connection refresh**: HTTP client recreated between retries to clear stale state

**User experience:**
When a network error occurs, you'll see:
```
⚠️  Network error: Connection timeout
   Retrying in 1.2s (attempt 1/3)...
```

The agent automatically recovers once connectivity is restored. Network resilience is always enabled and requires no configuration.

**Timeout configuration:**
```bash
export PATCHPAL_LLM_TIMEOUT=300              # Overall request timeout (default: 300s = 5 minutes)
                                              # Allows long operations while socket timeouts detect dead connections
```

### Context Window Management

```bash
# Auto-Compaction
export PATCHPAL_DISABLE_AUTOCOMPACT=true     # Disable auto-compaction (default: false - enabled)
export PATCHPAL_COMPACT_THRESHOLD=0.75       # Trigger compaction at % full (default: 0.75 = 75%)

# Context Limits
export PATCHPAL_CONTEXT_LIMIT=100000         # Override model's context limit (for testing)
                                              # Leave unset to use model's actual capacity

# Pruning Controls
export PATCHPAL_PROACTIVE_PRUNING=true       # Prune tool outputs after calls when > PRUNE_PROTECT (default: true)
                                              # Uses intelligent summarization to preserve context
export PATCHPAL_PRUNE_PROTECT=40000          # Keep last N tokens of tool outputs (default: 40000)
export PATCHPAL_PRUNE_MINIMUM=20000          # Minimum tokens to prune (default: 20000)
```

### MCP (Model Context Protocol) Integration

```bash
# Enable/Disable MCP Tools
export PATCHPAL_ENABLE_MCP=false             # Disable MCP tool loading (default: true - enabled)
                                              # Useful for: testing, faster startup, minimal environments
                                              # Note: MCP tools are loaded dynamically from ~/.patchpal/config.json
```

### Minimal Tools Mode

```bash
# Limit to Essential Tools Only
export PATCHPAL_MINIMAL_TOOLS=true           # Enable minimal tools mode (default: false)
                                              # Limits agent to 5 essential tools: read_file, edit_file, write_file, run_shell, grep
                                              # Recommended for: local models <20B params, models that struggle with tool selection
                                              # Improves: decision speed (2-3s vs 10-30s), tool accuracy (~95% vs ~60%)
                                              # Trade-off: No code_structure, web tools, TODO tools, etc.
```

### Web Tools

```bash
# Enable/Disable Web Access
export PATCHPAL_ENABLE_WEB=false             # Disable web search/fetch for air-gapped environments (default: true)

# SSL Certificate Verification (for web_search)
export PATCHPAL_VERIFY_SSL=true              # SSL verification for web searches (default: true)
                                              # Set to 'false' to disable (not recommended for production)
                                              # Or set to path of CA bundle file for corporate certificates
                                              # Auto-detects SSL_CERT_FILE and REQUESTS_CA_BUNDLE if not set
                                              # Examples:
                                              #   export PATCHPAL_VERIFY_SSL=false  # Disable verification
                                              #   export PATCHPAL_VERIFY_SSL=/path/to/ca-bundle.crt  # Custom CA bundle
                                              #   (Leave unset to auto-detect from SSL_CERT_FILE/REQUESTS_CA_BUNDLE)

# Web Request Limits
export PATCHPAL_WEB_TIMEOUT=60               # Web request timeout in seconds (default: 30)
export PATCHPAL_MAX_WEB_SIZE=10485760        # Max web content size in bytes (default: 5MB)
                                              # Character limits are controlled by PATCHPAL_MAX_TOOL_OUTPUT_CHARS
```

### Custom System Prompt

```bash
export PATCHPAL_SYSTEM_PROMPT=~/.patchpal/my_prompt.md  # Use custom system prompt
                                                          # File can use template variables: {platform_info}, {web_usage}
                                                          # Useful for: custom behavior, team standards, domain-specific instructions
```

### Configuration Examples

**Air-Gapped Environment (Offline, No Web Access):**
```bash
export PATCHPAL_ENABLE_WEB=false
patchpal --model hosted_vllm/openai/gpt-oss-120b
```

**Reasoning Model with High Effort:**
```bash
export PATCHPAL_MODEL=ollama_chat/gpt-oss:120b
export PATCHPAL_LITELLM_KWARGS='{"reasoning_effort": "high"}'
patchpal
```

**Maximum Security:**
```bash
# Single flag for all security restrictions
patchpal --maximum-security
# Enables: permission for all ops, repo-only access, web disabled
```

**Read-Only Mode (No File Modifications):**
```bash
export PATCHPAL_READ_ONLY=true
patchpal
# Agent can read files and run commands but cannot modify files
```

**Testing Context Management:**
```bash
export PATCHPAL_CONTEXT_LIMIT=10000          # Small limit to trigger compaction quickly
export PATCHPAL_COMPACT_THRESHOLD=0.75       # Trigger at 75% instead of 85%
export PATCHPAL_PRUNE_PROTECT=500            # Keep only last 500 tokens
patchpal
```

**Autonomous Mode (Trusted Environment Only):**
```bash
export PATCHPAL_REQUIRE_PERMISSION=false     # ⚠️  Disables all permission prompts
export PATCHPAL_MAX_ITERATIONS=200           # Allow longer runs
patchpal
```

**Autopilot Mode (CI/CD Integration):**
```bash
export PATCHPAL_AUTOPILOT_CONFIRMED=true     # Skip autopilot safety confirmation (default: false)
                                              # ⚠️  Only use in CI/CD or automation contexts
                                              # Autopilot mode allows continuous iterative execution
patchpal autopilot "Implement feature X"
```

**Image Analysis with Vision Models:**
```bash
# Anthropic/Claude (5MB limit via Bedrock or Direct API)
export PATCHPAL_MODEL=anthropic/claude-3-5-sonnet-20241022
patchpal

# OpenAI/GPT-4o (20MB limit)
export PATCHPAL_MODEL=openai/gpt-4o
patchpal

# Both work the same way from user perspective:
You: Look at screenshot.png and explain what's wrong

# The agent automatically:
# - Detects the model provider
# - Formats images appropriately:
#   * Anthropic: multimodal content in tool results
#   * OpenAI: images injected as user messages (API workaround)

# For images exceeding provider limits, increase PatchPal's limit:
export PATCHPAL_MAX_IMAGE_SIZE=$((20*1024*1024))  # 20MB

# Tip: Use compressed images (1-2MB) for faster processing
# Vision APIs resize large images automatically anyway

# Block images for non-vision models (or for privacy):
export PATCHPAL_BLOCK_IMAGES=true                # Replace images with text placeholders (default: false)
                                                 # Useful for:
                                                 # - Non-vision models (gpt-3.5-turbo, claude-instant, local models)
                                                 # - Privacy compliance (prevent image data from being sent)
                                                 # Images are replaced with: "[Image blocked - PATCHPAL_BLOCK_IMAGES=true...]"
```
