# Sandbox Mode

**Sandbox mode** runs PatchPal inside an isolated Docker or Podman container, providing security boundaries for AI agent operations. This is the **recommended** way to run PatchPal, especially for autopilot mode or when working with untrusted code.

## Quick Start

```bash
# Interactive mode (with permissions enabled)
patchpal-sandbox --env-file .env -- --model anthropic/claude-sonnet-4-5

# Autopilot mode (permissions disabled automatically)
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file task.md

# With local Ollama model
patchpal-sandbox --host-network -- --model ollama_chat/llama3.2
```

The `--` separator distinguishes sandbox options (left side) from PatchPal arguments (right side).

## Why Use Sandbox Mode?

### Security Benefits

**1. Ephemeral Filesystem**
- Container is destroyed after each session (`--rm` flag)
- Malicious code can't persist backdoors
- File modifications isolated to mounted `/workspace`

**2. Network Isolation** (with `--restrict-network`)
- Blocks data exfiltration attempts
- Prevents backdoor downloads
- Allows only whitelisted endpoints

**3. Resource Limits**
- Memory and CPU constraints prevent resource exhaustion
- Protects host system from runaway processes

**4. Process Isolation**
- Agent runs in separate namespace
- Can't access host processes or system files (outside mounts)

### Convenience Benefits

- ✅ Pre-built image with patchpal installed (fast startup)
- ✅ Auto-detects Docker/Podman (prefers Podman rootless)
- ✅ Auto-configures Ollama context lengths
- ✅ Loads API keys from `.env` files
- ✅ Mounts custom tools automatically
- ✅ Clean environment on each run

## Installation

No separate installation needed - `patchpal-sandbox` is included with PatchPal:

```bash
pip install patchpal
patchpal-sandbox --help
```

**First Run**: Downloads pre-built container image (~150MB, one-time)
**Subsequent Runs**: Start instantly (no pip install needed)

## Basic Usage

### Interactive Mode (Permissions Enabled)

```bash
# Using .env file for API keys
patchpal-sandbox --env-file .env -- --model anthropic/claude-sonnet-4-5

# Passing API key directly
patchpal-sandbox -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY -- --model anthropic/claude-sonnet-4-5

# Using multiple .env files
patchpal-sandbox --env-file .env --env-file .env.local -- --model openai/gpt-5-mini
```

### Autopilot Mode (Permissions Disabled Automatically)

```bash
# From prompt file
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file task.md \
  --max-iterations 30

# Inline prompt
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt "Build a calculator with tests"
```

See [Autopilot Mode](autopilot.md) for comprehensive autopilot documentation.

### Local Models (Ollama)

When using local Ollama models, use `--host-network` to access the host's Ollama service:

```bash
patchpal-sandbox --host-network -- --model ollama_chat/llama3.2

# Autopilot with Ollama
patchpal-sandbox --host-network -- autopilot \
  --model ollama_chat/gpt-oss:120b \
  --prompt-file task.md
```

**Note**: `--host-network` shares the host's network stack with the container (required for `localhost:11434` access). This bypasses network isolation.

## Network Restrictions

For maximum security, use `--restrict-network` to isolate the container from the internet while allowing access to required LLM APIs:

```bash
# Auto-detects LLM endpoints from environment variables
patchpal-sandbox \
  --restrict-network \
  --env-file .env \
  -- autopilot --prompt-file task.md

# With custom allowed URLs
patchpal-sandbox \
  --restrict-network \
  --allow-url https://api.openai.com \
  --allow-url https://custom-api.example.com \
  --env-file .env \
  -- autopilot --prompt-file task.md
```

### What Gets Blocked

With `--restrict-network`, the firewall blocks:
- ❌ GitHub, PyPI, npm, Docker Hub
- ❌ General internet access (google.com, etc.)
- ❌ Data exfiltration attempts
- ❌ Backdoor downloads

### What Stays Allowed

- ✅ Localhost (127.0.0.1/8)
- ✅ DNS queries
- ✅ Auto-detected LLM provider APIs
- ✅ URLs specified with `--allow-url`

### Auto-Detected LLM Endpoints

The sandbox automatically detects and allows these endpoints based on your environment variables:

| Provider | Environment Variable | Endpoint Allowed |
|----------|---------------------|------------------|
| OpenAI | `OPENAI_API_KEY` | `https://api.openai.com` |
| Anthropic | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` |
| Google AI | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com` |
| AWS Bedrock | `AWS_REGION` | Region-specific endpoint |
| Azure OpenAI | `AZURE_OPENAI_RESOURCE` | `https://<resource>.openai.azure.com` |
| Groq | `GROQ_API_KEY` | `https://api.groq.com` |
| Cohere | `COHERE_API_KEY` | `https://api.cohere.ai` |
| Together | `TOGETHER_API_KEY` | `https://api.together.xyz` |
| Replicate | `REPLICATE_API_KEY` | `https://api.replicate.com` |

Custom endpoints are also detected from variables like:
- `OPENAI_BASE_URL`, `OPENAI_API_BASE`, `OPENAI_ENDPOINT`
- `ANTHROPIC_BASE_URL`, `ANTHROPIC_API_BASE`
- `AWS_BEDROCK_ENDPOINT`, `AWS_ENDPOINT_URL_BEDROCK_RUNTIME`
- Any `*_BASE_URL`, `*_API_BASE`, `*_ENDPOINT` pattern

### Testing Network Restrictions

Validate firewall rules without running PatchPal:

```bash
patchpal-sandbox \
  --restrict-network \
  --test-restrictions \
  --env-file .env
```

This tests that:
- Blocked sites (google.com, github.com) are inaccessible
- Allowed LLM endpoints are accessible
- Returns exit code 0 on success, 1 on failure

### AWS Bedrock GovCloud Example

```bash
# .env.govcloud file:
# AWS_ACCESS_KEY_ID=...
# AWS_SECRET_ACCESS_KEY=...
# AWS_BEDROCK_REGION=us-gov-east-1

patchpal-sandbox \
  --restrict-network \
  --env-file .env.govcloud \
  -- autopilot \
  --model bedrock/arn:aws-us-gov:bedrock:us-gov-east-1::inference-profile/us-gov.anthropic.claude-sonnet-4-5-20250929-v1:0 \
  --prompt-file task.md
```

The sandbox automatically detects `us-gov-east-1` and allows `https://bedrock-runtime.us-gov-east-1.amazonaws.com`.

### Security Considerations

⚠️ **Container credentials**: AWS credentials passed via `--env-file` are visible to the container. However:
  - Exfiltration is still blocked by network restrictions
  - Credentials don't persist after container exit
  - Only affects that specific session

For maximum security:
- Use short-lived credentials (IAM roles, temporary tokens)
- Use restrictive IAM policies (minimum required permissions)
- Monitor AWS CloudTrail for unexpected API calls

## Advanced Options

### Container Runtime Selection

```bash
# Force Docker (default: auto-detect)
patchpal-sandbox --runtime docker -- --model anthropic/claude-sonnet-4-5

# Force Podman
patchpal-sandbox --runtime podman -- --model anthropic/claude-sonnet-4-5
```

**Auto-detection logic**:
1. Check if `podman` is available → use Podman rootless
2. Fallback to `docker`

### Custom Container Image

```bash
# Use latest PyPI version (slower startup - requires pip install)
patchpal-sandbox --image python:3.11-slim -- --model anthropic/claude-sonnet-4-5

# Use specific patchpal version
patchpal-sandbox --image ghcr.io/amaiya/patchpal-sandbox:0.21.8 -- --model anthropic/claude-sonnet-4-5
```

**Default image**: `ghcr.io/amaiya/patchpal-sandbox:latest` (pre-built, fast startup)

### Additional Volume Mounts

```bash
# Mount additional directories
patchpal-sandbox \
  -v /path/to/data:/data:ro \
  -v /path/to/output:/output \
  -- --model anthropic/claude-sonnet-4-5
```

### Environment Variables

Environment variable behavior depends on whether `--env-file` is provided:

**Without `--env-file` (uses host environment):**
```bash
# Host environment variables (AWS_*, OPENAI_*, etc.) are passed through
patchpal-sandbox -- --model openai/gpt-5-mini
```

**With `--env-file` (isolated mode):**
```bash
# ONLY variables from .env file are used (better isolation)
# Host environment variables are NOT passed
patchpal-sandbox --env-file .env -- --model anthropic/claude-sonnet-4-5

# Multiple .env files (later files override earlier)
patchpal-sandbox \
  --env-file .env.base \
  --env-file .env.local \
  -- --model anthropic/claude-sonnet-4-5
```

**Note**: When using `--env-file`, host environment variables are intentionally excluded for better security isolation. This prevents accidental credential leakage from your shell environment.

### Resource Limits

```bash
# Memory and CPU limits
patchpal-sandbox \
  --memory 4g \
  --cpus 2 \
  -- autopilot --prompt-file task.md
```

## Custom Tools

Custom tools work automatically in sandbox mode:

- **Global tools**: `~/.patchpal/tools/` (auto-mounted)
- **Repository tools**: `<repo>/.patchpal/tools/` (in `/workspace`)

See [Custom Tools](../features/custom-tools.md) for details on creating tools.

## Troubleshooting

### "docker: command not found"

Install Docker or Podman:

```bash
# Ubuntu/Debian
sudo apt-get install podman

# macOS
brew install podman
podman machine init
podman machine start

# RHEL/Fedora
sudo dnf install podman
```

### "Permission denied" errors

**Podman rootless** (recommended): No sudo required, works out of the box.

**Docker**: Add your user to the docker group:
```bash
sudo usermod -aG docker $USER
# Log out and back in
```

### Firewall rules not working

If `--restrict-network` isn't blocking traffic:

1. **Check container runtime capabilities**:
   ```bash
   # Podman rootless needs --privileged
   # (automatically added by patchpal-sandbox)
   ```

2. **Test restrictions explicitly**:
   ```bash
   patchpal-sandbox --restrict-network --test-restrictions --env-file .env
   ```

3. **Verify iptables inside container**:
   ```bash
   patchpal-sandbox --restrict-network --shell
   $ iptables -L -n
   ```

### Ollama connection refused

Use `--host-network` to access host's Ollama service:

```bash
patchpal-sandbox --host-network -- --model ollama_chat/llama3.2
```

### Slow startup times

**Solution 1**: Use pre-built image (default):
```bash
patchpal-sandbox -- --model anthropic/claude-sonnet-4-5
# First run: ~10s (image download, one-time)
# Subsequent: <1s
```

**Solution 2**: Pre-pull the image:
```bash
docker pull ghcr.io/amaiya/patchpal-sandbox:latest
# or
podman pull ghcr.io/amaiya/patchpal-sandbox:latest
```

### Corporate proxy/firewall issues

If you're behind a corporate proxy:

```bash
# Pass proxy settings
patchpal-sandbox \
  -e HTTP_PROXY=$HTTP_PROXY \
  -e HTTPS_PROXY=$HTTPS_PROXY \
  -e NO_PROXY=$NO_PROXY \
  -- --model anthropic/claude-sonnet-4-5
```

SSL certificates are auto-mounted from:
- `/etc/ssl/certs/ca-certificates.crt`
- `/etc/pki/tls/certs/ca-bundle.crt`
- `/etc/ssl/ca-bundle.pem`

## Comparison with Manual Docker/Podman

### Using patchpal-sandbox (Recommended)

```bash
patchpal-sandbox --env-file .env -- autopilot --prompt-file task.md
```

✅ Automatic container setup
✅ Pre-built image (fast startup)
✅ Auto-detects runtime (Podman/Docker)
✅ Auto-configures Ollama context
✅ Auto-mounts custom tools
✅ Auto-mounts SSL certs
✅ Network restriction support

### Manual Docker Command

```bash
docker run -it --rm \
  -v $(pwd):/workspace \
  -v ~/.patchpal:/root/.patchpal \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  --memory="2g" --cpus="2" \
  ghcr.io/amaiya/patchpal-sandbox:latest \
  bash -c "patchpal-autopilot --prompt-file task.md"
```

❌ More verbose
❌ Manual volume mounts
❌ Manual environment setup
❌ No auto-detection
❌ No network restrictions

**Recommendation**: Use `patchpal-sandbox` for simplicity and consistency.

## Best Practices

### Always Use Sandbox For

- ✅ Autopilot mode (REQUIRED for safety)
- ✅ Untrusted code/repositories
- ✅ Automated workflows
- ✅ Production environments
- ✅ Repositories with sensitive data

### Consider Sandbox For

- ✅ General development (extra safety layer)
- ✅ Testing/experimentation
- ✅ Learning PatchPal

### Optional Without Sandbox

- Direct use on trusted throwaway projects
- One-off interactive sessions on isolated VMs
- Cases where you need direct host access

### Network Restriction Recommendations

| Scenario | Use `--restrict-network`? |
|----------|---------------------------|
| Autopilot mode | ✅ **YES** (strongly recommended) |
| Untrusted code | ✅ **YES** |
| Production automation | ✅ **YES** |
| Personal projects | ⚠️ Optional (adds defense-in-depth) |
| Trusted code + human oversight | ⚠️ Optional |
| Local models only (Ollama) | ❌ NO (requires `--host-network`) |

## Examples

### Multi-Phase Project

```bash
# Phase 1: Core functionality
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file phase1.md

# Phase 2: Tests
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file phase2.md

# Phase 3: Documentation
patchpal-sandbox --env-file .env -- autopilot \
  --model anthropic/claude-sonnet-4-5 \
  --prompt-file phase3.md
```

### Debugging Inside Container

```bash
# Start shell inside container with model pre-configured
patchpal-sandbox --env-file .env --shell -- --model anthropic/claude-sonnet-4-5

# Inside container
$ pwd
/workspace

$ ls -la ~/.patchpal/tools/
# Your custom tools are here

$ echo $PATCHPAL_MODEL
anthropic/claude-sonnet-4-5

$ patchpal
# Runs with the pre-configured model automatically
```

**Tip**: When you provide `--model` after `--`, it's automatically set as the `PATCHPAL_MODEL` environment variable, so you can run `patchpal` without specifying the model again.

## Learn More

- [Autopilot Mode](autopilot.md) - Comprehensive autopilot documentation
- [Configuration](../configuration.md) - Environment variables and settings
- [Custom Tools](../features/custom-tools.md) - Creating custom tool integrations
- [Safety](../safety.md) - Security best practices
- [Examples: Ralph](https://github.com/amaiya/patchpal/tree/main/examples/ralph) - Real-world autopilot examples
