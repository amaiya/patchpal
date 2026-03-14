#!/bin/bash
# Run PatchPal in an isolated Docker/Podman container for safety
#
# This script provides resource isolation and runs PatchPal in a clean
# container environment. Recommended for:
# - Autopilot mode
# - Testing untrusted code
# - High-risk operations

set -e

# Default configuration
SANDBOX_IMAGE="python:3.11-slim"
SANDBOX_NETWORK="bridge"  # Network enabled by default (needed for cloud LLMs)
SANDBOX_MEMORY=""  # No limit by default (Docker/Podman defaults)
SANDBOX_CPUS=""    # No limit by default (Docker/Podman defaults)
ENV_FILE=""        # Optional .env file to load

# Function to load .env file
load_env_file() {
    local env_file="$1"
    if [ ! -f "$env_file" ]; then
        echo "Error: .env file not found: $env_file" >&2
        exit 1
    fi

    # Export variables from .env file (ignore comments and empty lines)
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^#.*$ ]] && continue
        [[ -z "$key" ]] && continue

        # Remove leading/trailing whitespace
        key=$(echo "$key" | xargs)
        value=$(echo "$value" | xargs)

        # Remove quotes from value if present
        value="${value%\"}"
        value="${value#\"}"
        value="${value%\'}"
        value="${value#\'}"

        # Export the variable
        export "$key=$value"
    done < "$env_file"
}

# Show help if requested
show_help() {
    cat << 'EOF'
sandbox-patchpal.sh - Run PatchPal in an isolated container

USAGE:
    ./scripts/sandbox-patchpal.sh [SCRIPT_OPTIONS] -- [PATCHPAL_ARGS...]

    Note: Script options must come BEFORE the '--' separator.
          PatchPal options must come AFTER the '--' separator.

DESCRIPTION:
    Runs PatchPal inside a Docker/Podman container with:
    - Network access (required for cloud LLMs like OpenAI, Anthropic)
    - No resource limits by default (uses Docker/Podman defaults)
    - Current directory mounted as /workspace
    - Auto-installs patchpal in container

    Recommended for autopilot mode and high-risk operations.

SCRIPT OPTIONS:
      --image IMAGE       Container image to use (default: python:3.11-slim)
      --no-network        Disable network access (incompatible with cloud LLMs)
      --host-network      Use host network (required for local Ollama/vLLM servers)
      --memory LIMIT      Memory limit (e.g., 2g, 4g) - optional, no limit by default
      --cpus NUM          CPU limit (e.g., 2, 4) - optional, no limit by default
      --env-file FILE     Load environment variables from .env file
      -h, --help          Show this help message

EXAMPLES:
      # Load API keys from .env file
      ./scripts/sandbox-patchpal.sh --env-file .env -- --model openai/gpt-5.2-codex
      ./scripts/sandbox-patchpal.sh --env-file ~/.config/patchpal/.env -- --model anthropic/claude-sonnet-4-5

      # Basic usage with cloud LLM (network enabled by default)
      ./scripts/sandbox-patchpal.sh -- --model openai/gpt-5.2-codex

    # With local model (Ollama) - requires host network to reach Ollama on localhost
    ./scripts/sandbox-patchpal.sh --host-network -- --model ollama_chat/llama3.1

    # With Anthropic Claude
    ./scripts/sandbox-patchpal.sh -- --model anthropic/claude-sonnet-4-5

    # Disable network for maximum isolation (not usable for any LLMs)
    ./scripts/sandbox-patchpal.sh --no-network -- --model local_only_model

    # Use different Python version
    ./scripts/sandbox-patchpal.sh --image python:3.12 -- --model openai/gpt-5.2-codex

    # More resources for larger models
    ./scripts/sandbox-patchpal.sh --memory 8g --cpus 4 -- --model ollama_chat/gpt-oss:120b

    # Limit resources if needed
    ./scripts/sandbox-patchpal.sh --memory 2g --cpus 2 -- --model ollama_chat/llama3.1

    # Autopilot mode (disable permissions via environment variable)
    PATCHPAL_REQUIRE_PERMISSION=false ./scripts/sandbox-patchpal.sh -- --model openai/gpt-5.2-codex

ENVIRONMENT VARIABLES:
      The following environment variables are automatically passed to the container:

      - All PATCHPAL_* variables (e.g., PATCHPAL_REQUIRE_PERMISSION)
      - All OPENAI_* variables (e.g., OPENAI_API_KEY, OPENAI_BASE_URL)
      - All ANTHROPIC_* variables (e.g., ANTHROPIC_API_KEY)
      - All AWS_* variables (e.g., AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
      - All AZURE_* variables (e.g., AZURE_OPENAI_KEY, AZURE_OPENAI_ENDPOINT)
      - All GOOGLE_* variables (e.g., GOOGLE_API_KEY)
      - All GROQ_* variables (e.g., GROQ_API_KEY)
      - All COHERE_* variables (e.g., COHERE_API_KEY)
      - All HUGGINGFACE_* variables (e.g., HUGGINGFACE_API_KEY)
      - All REPLICATE_* variables (e.g., REPLICATE_API_TOKEN)
      - All TOGETHER_* variables (e.g., TOGETHER_API_KEY)
      - SSL_CERT_FILE and REQUESTS_CA_BUNDLE (auto-mounted if paths exist)

      You can load these from a .env file using --env-file:

      Example .env file:
          # API Keys
          OPENAI_API_KEY=sk-your-key-here
          ANTHROPIC_API_KEY=sk-ant-your-key-here

          # Custom endpoints (optional)
          OPENAI_BASE_URL=https://your-proxy.com/v1

          # Disable permissions for autopilot
          PATCHPAL_REQUIRE_PERMISSION=false

      Note: SSL_CERT_FILE and REQUESTS_CA_BUNDLE paths are auto-mounted if they exist.

CONTAINER RUNTIME:
    Auto-detects Docker or Podman. Podman preferred (rootless).
    - Linux/WSL: Runs containers directly
    - macOS/Windows: Auto-starts Podman machine if needed

SECURITY:
    - Network enabled by default (needed for cloud LLMs and web tools)
    - No resource limits by default (trust Docker/Podman and OS limits)
    - Clean environment on each run (--rm flag)
    - Workspace files visible but container has limited privileges

NOTES:
    - First run downloads the Python image (~130MB)
    - Each run reinstalls patchpal (takes ~10s)
    - Current directory mounted at /workspace (read-write)
    - ~/.patchpal mounted at /root/.patchpal if it exists
    - SSL certificates auto-mounted from /etc/ssl/certs if present
    - Files in /workspace persist on host, other files are lost on exit
    - Container ~ = /root (not your host home directory)
    - Use --no-network for maximum isolation with local models only

CORPORATE NETWORKS (Linux/WSL):
    If you get SSL certificate errors behind a corporate proxy/firewall:

    1. Ensure your custom CA cert is in /etc/ssl/certs/ca-certificates.crt
       (The script auto-mounts this if it exists on Linux/WSL)

    2. Or set environment variables pointing to your cert:
       export SSL_CERT_FILE=/path/to/your/ca-bundle.crt
       ./scripts/sandbox-patchpal.sh -- --model openai/gpt-5.2-codex

    On macOS/Windows: Docker Desktop handles certificates differently.
    You may need to add certificates to Docker Desktop's trusted CAs.

SEE ALSO:
    - docs/usage/autopilot.md - Autopilot safety guidelines
    - docs/sandboxing.md - Full sandboxing strategy
EOF
}

# Parse script-specific arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --image)
            SANDBOX_IMAGE="$2"
            shift 2
            ;;
        --no-network)
            SANDBOX_NETWORK="none"
            shift
            ;;
        --host-network)
            SANDBOX_NETWORK="host"
            shift
            ;;
        --memory)
            SANDBOX_MEMORY="$2"
            shift 2
            ;;
        --cpus)
            SANDBOX_CPUS="$2"
            shift 2
            ;;
        --env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        --)
            shift
            break
            ;;
        *)
            # Assume remaining args are for patchpal
            break
            ;;
    esac
done

# Load .env file if specified
if [ -n "$ENV_FILE" ]; then
    echo "Loading environment variables from: $ENV_FILE"
    load_env_file "$ENV_FILE"
fi

# Auto-detect container runtime (prefer podman for rootless, fallback to docker)
detect_runtime() {
    if command -v podman &> /dev/null; then
        echo "podman"
    elif command -v docker &> /dev/null; then
        echo "docker"
    else
        echo ""
    fi
}

RUNTIME=$(detect_runtime)

if [ -z "$RUNTIME" ]; then
    echo "Error: Neither Docker nor Podman found."
    echo "Please install one of:"
    echo "  - Docker: https://docs.docker.com/get-docker/"
    echo "  - Podman: https://podman.io/getting-started/installation"
    exit 1
fi

# For Podman on macOS/Windows, ensure the machine is running
if [ "$RUNTIME" = "podman" ]; then
    # Check if podman machine is needed (macOS/Windows)
    # In WSL/Linux, 'podman machine list' may exist but return empty - skip if no machines defined
    if podman machine list &>/dev/null; then
        MACHINE_COUNT=$(podman machine list --format "{{.Name}}" 2>/dev/null | wc -l)
        if [ "$MACHINE_COUNT" -gt 0 ]; then
            # Machines are defined, check if any are running
            if ! podman machine list --format "{{.Running}}" 2>/dev/null | grep -q "true"; then
                echo "Podman machine not running. Starting default machine..."
                podman machine start 2>/dev/null || {
                    echo "Warning: Could not start podman machine automatically."
                    echo "Please run: podman machine start"
                    exit 1
                }
            fi
        fi
        # If MACHINE_COUNT is 0, skip machine checks (WSL/Linux native mode)
    fi
fi

echo "Using container runtime: $RUNTIME"
echo "Image: $SANDBOX_IMAGE"
echo "Network: $SANDBOX_NETWORK"
if [ -n "$SANDBOX_MEMORY" ]; then
    echo "Memory limit: $SANDBOX_MEMORY"
fi
if [ -n "$SANDBOX_CPUS" ]; then
    echo "CPU limit: $SANDBOX_CPUS"
fi
echo "Workspace: $(pwd)"
echo ""

# Check if image exists, pull if not
if ! $RUNTIME image exists "$SANDBOX_IMAGE" 2>/dev/null; then
    echo "Image $SANDBOX_IMAGE not found locally. Pulling..."
    $RUNTIME pull "$SANDBOX_IMAGE"
fi

# Build container arguments
CONTAINER_ARGS=(
    "-it" "--rm"
    "--network" "$SANDBOX_NETWORK"
    "-v" "$(pwd):/workspace"
    "-w" "/workspace"
)

# Pass through all PATCHPAL_* environment variables
while IFS='=' read -r name value; do
    if [[ "$name" =~ ^PATCHPAL_ ]]; then
        CONTAINER_ARGS+=("-e" "$name=$value")
    fi
done < <(env)

# Pass through common LLM and cloud provider API keys/config (pattern matching)
while IFS='=' read -r name value; do
    if [[ "$name" =~ ^(OPENAI|ANTHROPIC|AWS|AZURE|GOOGLE|GROQ|COHERE|HUGGINGFACE|REPLICATE|TOGETHER)_ ]]; then
        CONTAINER_ARGS+=("-e" "$name=$value")
    fi
done < <(env)

# Track mounted paths to avoid duplicates
declare -A MOUNTED_PATHS

# Mount ~/.patchpal if it exists (for custom tools, config, memory, logs)
if [ -d "$HOME/.patchpal" ]; then
    CONTAINER_ARGS+=("-v" "$HOME/.patchpal:/root/.patchpal")
    MOUNTED_PATHS["$HOME/.patchpal"]=1
fi

# Mount SSL certificates if they exist (for corporate proxies/firewalls)
if [ -f "/etc/ssl/certs/ca-certificates.crt" ]; then
    CONTAINER_ARGS+=("-v" "/etc/ssl/certs/ca-certificates.crt:/etc/ssl/certs/ca-certificates.crt:ro")
    MOUNTED_PATHS["/etc/ssl/certs/ca-certificates.crt"]=1
fi
if [ -d "/usr/local/share/ca-certificates" ] && [ -n "$(ls -A /usr/local/share/ca-certificates 2>/dev/null)" ]; then
    CONTAINER_ARGS+=("-v" "/usr/local/share/ca-certificates:/usr/local/share/ca-certificates:ro")
    MOUNTED_PATHS["/usr/local/share/ca-certificates"]=1
fi

# Pass through SSL-related environment variables and mount the cert files (avoid duplicates)
if [ -n "$SSL_CERT_FILE" ] && [ -f "$SSL_CERT_FILE" ]; then
    if [ -z "${MOUNTED_PATHS[$SSL_CERT_FILE]}" ]; then
        # Mount the cert file at the same path inside container
        CONTAINER_ARGS+=("-v" "$SSL_CERT_FILE:$SSL_CERT_FILE:ro")
        MOUNTED_PATHS["$SSL_CERT_FILE"]=1
    fi
    CONTAINER_ARGS+=("-e" "SSL_CERT_FILE=$SSL_CERT_FILE")
elif [ -n "$SSL_CERT_FILE" ]; then
    echo "Warning: SSL_CERT_FILE is set but file doesn't exist: $SSL_CERT_FILE"
fi

if [ -n "$REQUESTS_CA_BUNDLE" ] && [ -f "$REQUESTS_CA_BUNDLE" ]; then
    if [ -z "${MOUNTED_PATHS[$REQUESTS_CA_BUNDLE]}" ]; then
        # Mount the cert file at the same path inside container
        CONTAINER_ARGS+=("-v" "$REQUESTS_CA_BUNDLE:$REQUESTS_CA_BUNDLE:ro")
        MOUNTED_PATHS["$REQUESTS_CA_BUNDLE"]=1
    fi
    CONTAINER_ARGS+=("-e" "REQUESTS_CA_BUNDLE=$REQUESTS_CA_BUNDLE")
elif [ -n "$REQUESTS_CA_BUNDLE" ]; then
    echo "Warning: REQUESTS_CA_BUNDLE is set but file doesn't exist: $REQUESTS_CA_BUNDLE"
fi

# Add resource limits if specified
if [ -n "$SANDBOX_MEMORY" ]; then
    CONTAINER_ARGS+=("--memory" "$SANDBOX_MEMORY")
fi
if [ -n "$SANDBOX_CPUS" ]; then
    CONTAINER_ARGS+=("--cpus" "$SANDBOX_CPUS")
fi

# Run PatchPal in container
exec $RUNTIME run "${CONTAINER_ARGS[@]}" \
    "$SANDBOX_IMAGE" \
    bash -c "pip install -q patchpal && patchpal $*"
