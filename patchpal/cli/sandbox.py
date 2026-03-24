#!/usr/bin/env python3
"""
PatchPal Sandbox - Run PatchPal in isolated Docker/Podman container

Provides sandboxed execution for both interactive and autopilot modes.

Usage:
    patchpal-sandbox --model openai/gpt-5.2-codex
    patchpal-sandbox --env-file .env -- autopilot --prompt "Fix the bug"
    patchpal-sandbox --host-network -- --model ollama_chat/llama3.1
"""

import argparse
import os
import shutil
import subprocess
import sys


def load_env_file(env_file):
    """Load environment variables from .env file."""
    if not os.path.exists(env_file):
        print(f"❌ Error: .env file not found: {env_file}", file=sys.stderr)
        sys.exit(1)

    with open(env_file, "r") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=VALUE
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Remove quotes if present
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                elif value.startswith("'") and value.endswith("'"):
                    value = value[1:-1]

                os.environ[key] = value


def detect_runtime():
    """Detect container runtime (podman or docker)."""
    if shutil.which("podman"):
        return "podman"
    elif shutil.which("docker"):
        return "docker"
    else:
        return None


def ensure_podman_machine(runtime):
    """Ensure Podman machine is running (macOS/Windows only)."""
    if runtime != "podman":
        return

    # Check if we're on Linux/WSL (no machine needed)
    try:
        result = subprocess.run(
            ["podman", "machine", "list"], capture_output=True, text=True, check=False
        )

        # If machine list is empty or command fails, we're on Linux (no machines)
        if result.returncode != 0 or not result.stdout.strip():
            return

        # Parse machine list to see if any are running
        lines = result.stdout.strip().split("\n")[1:]  # Skip header
        if not lines or not any(line for line in lines if line.strip()):
            return  # No machines (Linux/WSL)

        # Check if any machine is running
        running = any("running" in line.lower() for line in lines)

        if not running:
            print("Starting Podman machine...")
            subprocess.run(["podman", "machine", "start"], check=True)
    except Exception:
        # If anything fails, assume we don't need machines (Linux)
        pass


def is_interactive_command(patchpal_args):
    """Detect if running a non-interactive command."""
    if not patchpal_args:
        return True

    # Check for non-interactive flags
    for arg in patchpal_args:
        if arg in ["--version", "-v", "--help", "-h"]:
            return False

    # Check for autopilot
    if patchpal_args[0] in ["autopilot", "patchpal-autopilot"]:
        return False

    return True


def detect_llm_endpoints_from_env():
    """Detect LLM provider API endpoints from environment variables.

    Returns:
        list: List of detected endpoint URLs
    """
    detected_urls = []

    # Standard LLM provider API endpoints
    standard_endpoints = {
        "OPENAI_API_KEY": "https://api.openai.com",
        "ANTHROPIC_API_KEY": "https://api.anthropic.com",
        "GOOGLE_API_KEY": "https://generativelanguage.googleapis.com",
        "GROQ_API_KEY": "https://api.groq.com",
        "COHERE_API_KEY": "https://api.cohere.ai",
        "TOGETHER_API_KEY": "https://api.together.xyz",
        "REPLICATE_API_TOKEN": "https://api.replicate.com",
    }

    # Check for standard endpoints (if API key is set, add default URL)
    for env_var, default_url in standard_endpoints.items():
        if os.environ.get(env_var):
            detected_urls.append(default_url)

    # Check for custom endpoint URLs (these override defaults)
    custom_endpoint_vars = [
        "OPENAI_BASE_URL",
        "OPENAI_API_BASE",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_BASE",
        "AWS_BEDROCK_ENDPOINT",
        "AWS_ENDPOINT_URL_BEDROCK_RUNTIME",
        "AWS_ENDPOINT_URL",
        "AWS_BEDROCK_RUNTIME_ENDPOINT",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_API_BASE",
        "GOOGLE_API_BASE",
        "GROQ_API_BASE",
        "COHERE_API_BASE",
        "TOGETHER_API_BASE",
        "REPLICATE_API_BASE",
        "HUGGINGFACE_API_BASE",
    ]

    for env_var in custom_endpoint_vars:
        value = os.environ.get(env_var)
        if value:
            # Ensure it's a valid URL
            if value.startswith("http://") or value.startswith("https://"):
                detected_urls.append(value)
            else:
                # Assume https if no protocol specified
                detected_urls.append(f"https://{value}")

    # AWS Bedrock: Check for region-based endpoints
    # Check multiple region variables in order of precedence (matching function_calling.py)
    aws_region = (
        os.environ.get("AWS_BEDROCK_REGION")
        or os.environ.get("AWS_REGION")
        or os.environ.get("AWS_DEFAULT_REGION")
    )
    if aws_region and (
        os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("AWS_SECRET_ACCESS_KEY")
    ):
        # Add Bedrock endpoint for the region
        # Support both GovCloud and standard regions
        # Also support AWS China regions
        if "gov" in aws_region:
            # GovCloud regions use FIPS endpoints
            detected_urls.append(f"https://bedrock-runtime-fips.{aws_region}.amazonaws.com")
        elif "cn-" in aws_region:
            # AWS China regions use .amazonaws.com.cn
            detected_urls.append(f"https://bedrock-runtime.{aws_region}.amazonaws.com.cn")
        else:
            # Standard commercial regions
            detected_urls.append(f"https://bedrock-runtime.{aws_region}.amazonaws.com")

    # Azure OpenAI: Extract from resource name if AZURE_OPENAI_KEY is set
    azure_key = os.environ.get("AZURE_OPENAI_KEY") or os.environ.get("AZURE_API_KEY")
    if azure_key:
        # Try to get resource name from various env vars
        azure_resource = None
        for var in ["AZURE_OPENAI_RESOURCE", "AZURE_RESOURCE_NAME"]:
            azure_resource = os.environ.get(var)
            if azure_resource:
                break

        if azure_resource:
            detected_urls.append(f"https://{azure_resource}.openai.azure.com")

    # Deduplicate URLs
    return list(set(detected_urls))


def build_network_restriction_script(allowed_urls, test_mode=False):
    """Build bash script to configure iptables firewall for network restrictions."""
    script = """
echo "=== Pre-downloading required data (before network restrictions) ==="

# Try to pre-download tiktoken encodings (REQUIRED even for PatchPal 0.21.8+)
# LiteLLM still uses tiktoken internally for some models, and will try to download
# encodings from https://openaipublic.blob.core.windows.net/encodings/cl100k_base.tiktoken
# If we don't pre-download before setting up the firewall, PatchPal will hang trying to
# download it after the firewall blocks the connection.
echo "Pre-downloading tiktoken encodings (required for LiteLLM)..."
python3 << 'PYTHON_EOF' 2>&1 || echo "⚠ Tiktoken pre-download failed"
try:
    import tiktoken
    import os
    os.environ['TIKTOKEN_CACHE_DIR'] = '/tmp/tiktoken_cache'
    enc = tiktoken.encoding_for_model("gpt-4")
    enc.encode("test")
    print("✓ Tiktoken encodings cached successfully")
except ImportError as e:
    print(f"⚠ Tiktoken not installed: {e}")
except Exception as e:
    print(f"⚠ Tiktoken cache failed: {e}")
PYTHON_EOF

# Pre-import litellm to trigger model cost map download
echo "Downloading LiteLLM model cost map..."
python3 -c "import litellm; print('✓ LiteLLM initialized')" 2>/dev/null || echo "⚠ LiteLLM initialization failed"

echo ""
echo "=== Setting up network restrictions ==="

# Process allowed URLs and resolve IPs
ALLOWED_IPS=""
"""

    # Add URL resolution for each allowed URL
    for url in allowed_urls:
        script += f"""
# Resolve: {url}
URL="{url}"
HOSTNAME="${{URL#https://}}"
HOSTNAME="${{HOSTNAME#http://}}"
HOSTNAME="${{HOSTNAME%%/*}}"
echo "Resolving: $HOSTNAME"
IPS=$(getent hosts "$HOSTNAME" | awk '{{ print $1 }}' || true)
if [ -z "$IPS" ]; then
    echo "  WARNING: Could not resolve $HOSTNAME"
else
    echo "$IPS" | while read -r IP; do
        echo "  Resolved: $IP"
    done
    ALLOWED_IPS="$ALLOWED_IPS$IPS"$'\\n'
fi
"""

    script += """
# Deduplicate IPs
ALL_ALLOWED_IPS=$(echo -e "$ALLOWED_IPS" | sort -u | grep -v '^$')

# Install iptables if not available
if ! command -v iptables &> /dev/null; then
    echo "Installing iptables..."
    apt-get update -qq && apt-get install -y -qq iptables > /dev/null 2>&1
fi

# Configure iptables
echo "Configuring firewall rules..."

# Allow DNS (required for hostname resolution)
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# Allow localhost
iptables -A OUTPUT -d 127.0.0.1/8 -j ACCEPT
# Allow IPv6 localhost (if IPv6 is available)
ip6tables -A OUTPUT -d ::1/128 -j ACCEPT 2>/dev/null || true

# Allow each resolved IP
if [ -n "$ALL_ALLOWED_IPS" ]; then
    echo "Allowed IPs:"
    while IFS= read -r IP; do
        if [ -n "$IP" ]; then
            echo "  $IP (HTTPS)"
            iptables -A OUTPUT -d $IP -p tcp --dport 443 -j ACCEPT
        fi
    done <<< "$ALL_ALLOWED_IPS"
else
    echo "⚠ WARNING: No URLs resolved - all external network access will be blocked"
fi

# Allow established connections (for responses)
iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Log and drop everything else
iptables -A OUTPUT -j LOG --log-prefix "BLOCKED: " --log-level 4
iptables -A OUTPUT -j DROP

echo ""
echo "=== Firewall rules active ==="
iptables -L OUTPUT -n -v
echo ""
echo "Waiting for iptables rules to fully apply..."
sleep 1
echo "Network restrictions ready."
echo ""
"""

    # Add test mode if requested
    if test_mode:
        script += """
echo "=== Testing network restrictions ==="
echo ""

# Test 1: Blocked site (should fail)
echo "Test 1: Attempting to reach google.com (should be BLOCKED):"
if curl -m 5 -s https://google.com > /dev/null 2>&1; then
    echo "  ❌ FAILED: google.com was reachable (should be blocked)"
    exit 1
else
    echo "  ✓ PASSED: google.com blocked as expected"
fi
echo ""

# Test 2: Allowed URLs (should succeed)
"""
        for url in allowed_urls:
            hostname = url.replace("https://", "").replace("http://", "").split("/")[0]
            script += f"""
echo "Test 2: Attempting to reach {hostname} (should be ALLOWED):"
if curl -m 10 -s -I https://{hostname} > /dev/null 2>&1; then
    echo "  ✓ PASSED: {hostname} accessible as expected"
else
    echo "  ⚠ WARNING: {hostname} not reachable (may be a network issue)"
fi
echo ""
"""

        script += """
# Test 3: Another blocked site
echo "Test 3: Attempting to reach github.com (should be BLOCKED):"
if curl -m 5 -s https://github.com > /dev/null 2>&1; then
    echo "  ❌ FAILED: github.com was reachable (should be blocked)"
    exit 1
else
    echo "  ✓ PASSED: github.com blocked as expected"
fi
echo ""

echo "=== All network restriction tests PASSED ==="
echo ""
"""

    return script


def build_container_args(sandbox_args, patchpal_args):
    """Build container runtime arguments."""
    runtime = detect_runtime()
    if not runtime:
        print("❌ Error: Neither Docker nor Podman found", file=sys.stderr)
        print("\nPlease install Docker or Podman:", file=sys.stderr)
        print("  - Docker: https://docs.docker.com/get-docker/", file=sys.stderr)
        print("  - Podman: https://podman.io/getting-started/installation", file=sys.stderr)
        sys.exit(1)

    ensure_podman_machine(runtime)

    # Detect model from patchpal args to set appropriate context length
    model_name = None
    for i, arg in enumerate(patchpal_args):
        if arg == "--model" and i + 1 < len(patchpal_args):
            model_name = patchpal_args[i + 1]
            break

    # Set OLLAMA_CONTEXT_LENGTH if using Ollama and not already set
    if (
        model_name
        and ("ollama" in model_name.lower())
        and "OLLAMA_CONTEXT_LENGTH" not in os.environ
    ):
        # Check if it's a reasoning model
        reasoning_models = ["gpt-oss", "deepseek-r1", "qwq", "qwen"]
        is_reasoning = any(rm in model_name.lower() for rm in reasoning_models)

        if is_reasoning:
            os.environ["OLLAMA_CONTEXT_LENGTH"] = "32768"
            print("ℹ️  Auto-setting OLLAMA_CONTEXT_LENGTH=32768 for reasoning model")
        else:
            os.environ["OLLAMA_CONTEXT_LENGTH"] = "8192"
            print("ℹ️  Auto-setting OLLAMA_CONTEXT_LENGTH=8192 for Ollama model")

    # Base container arguments
    is_interactive = is_interactive_command(patchpal_args)
    container_args = [runtime, "run"]

    if is_interactive:
        container_args.extend(["-it"])
    else:
        container_args.extend(["-i"])

    container_args.extend(
        [
            "--rm",
            "--network",
            sandbox_args.network,
            "-v",
            f"{os.getcwd()}:/workspace",
            "-w",
            "/workspace",
        ]
    )

    # Add capabilities for network restrictions (iptables)
    if sandbox_args.restrict_network:
        # Check if running rootless podman
        needs_privileged = False
        if runtime == "podman":
            try:
                result = subprocess.run(
                    ["podman", "info"], capture_output=True, text=True, check=False
                )
                if "rootless: true" in result.stdout.lower():
                    needs_privileged = True
            except Exception:
                pass

        if needs_privileged:
            print("⚠️  Rootless Podman detected - using --privileged mode for iptables")
            container_args.extend(["--privileged"])
            container_args.extend(["--cgroup-manager=cgroupfs"])
        else:
            container_args.extend(["--cap-add=NET_ADMIN"])

    # Add resource limits if specified
    if sandbox_args.memory:
        container_args.extend(["--memory", sandbox_args.memory])
    if sandbox_args.cpus:
        container_args.extend(["--cpus", str(sandbox_args.cpus)])

    # Pass through PATCHPAL_* environment variables
    for key, value in os.environ.items():
        if key.startswith("PATCHPAL_"):
            container_args.extend(["-e", f"{key}={value}"])

    # Pass through LLM provider environment variables
    provider_prefixes = [
        "OPENAI",
        "ANTHROPIC",
        "AWS",
        "AZURE",
        "GOOGLE",
        "GROQ",
        "COHERE",
        "HUGGINGFACE",
        "REPLICATE",
        "TOGETHER",
    ]
    for key, value in os.environ.items():
        if any(key.startswith(prefix + "_") for prefix in provider_prefixes):
            container_args.extend(["-e", f"{key}={value}"])

    # Pass through OLLAMA_* environment variables (including OLLAMA_CONTEXT_LENGTH)
    # This allows you to set OLLAMA_API_BASE on the host to point to Ollama:
    #
    # For LOCAL Ollama on host machine:
    #   - Linux/WSL2 with mirrored networking: Use --host-network (container shares host network)
    #   - macOS/Windows Docker Desktop: export OLLAMA_API_BASE=http://host.docker.internal:11434
    #   - Podman: export OLLAMA_API_BASE=http://host.containers.internal:11434
    #
    # For REMOTE Ollama:
    #   export OLLAMA_API_BASE=http://192.168.1.100:11434
    #
    # The container will automatically receive OLLAMA_API_BASE environment variable.
    for key, value in os.environ.items():
        if key.startswith("OLLAMA_"):
            container_args.extend(["-e", f"{key}={value}"])

    # Track mounted paths to avoid duplicates
    mounted_paths = set()

    # Mount ~/.patchpal if it exists
    patchpal_dir = os.path.expanduser("~/.patchpal")
    if os.path.isdir(patchpal_dir):
        container_args.extend(["-v", f"{patchpal_dir}:/root/.patchpal"])
        mounted_paths.add(patchpal_dir)

    # Development mode: mount local patchpal source code
    dev_mode = False
    if sandbox_args.dev:
        # Check if we're in the patchpal repo (look for pyproject.toml or setup.py)
        repo_root = os.getcwd()
        if os.path.isfile(os.path.join(repo_root, "pyproject.toml")) or os.path.isfile(
            os.path.join(repo_root, "setup.py")
        ):
            # Mount the patchpal source directory
            container_args.extend(["-v", f"{repo_root}:/patchpal-dev"])
            dev_mode = True
            print("ℹ️  Development mode: Mounting local patchpal code from", repo_root)
        else:
            print(
                "⚠️  Warning: --dev flag used but not in patchpal repo root (no pyproject.toml or setup.py found)"
            )

    # Mount SSL certificates if they exist (Linux/WSL)
    ssl_cert_file = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.isfile(ssl_cert_file):
        container_args.extend(["-v", f"{ssl_cert_file}:{ssl_cert_file}:ro"])
        mounted_paths.add(ssl_cert_file)
        # Set environment variables so Python's requests library uses the mounted cert
        if "SSL_CERT_FILE" not in os.environ:
            container_args.extend(["-e", f"SSL_CERT_FILE={ssl_cert_file}"])
        if "REQUESTS_CA_BUNDLE" not in os.environ:
            container_args.extend(["-e", f"REQUESTS_CA_BUNDLE={ssl_cert_file}"])

    ssl_cert_dir = "/usr/local/share/ca-certificates"
    if os.path.isdir(ssl_cert_dir) and os.listdir(ssl_cert_dir):
        container_args.extend(["-v", f"{ssl_cert_dir}:{ssl_cert_dir}:ro"])
        mounted_paths.add(ssl_cert_dir)

    # Mount SSL_CERT_FILE, REQUESTS_CA_BUNDLE, and CURL_CA_BUNDLE if set
    # Map host cert files to /tmp inside container since parent dirs may not exist
    cert_mapping = {}  # Track host path -> container path mappings
    for env_var in ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"]:
        cert_path = os.environ.get(env_var)
        if cert_path and os.path.isfile(cert_path):
            if cert_path not in cert_mapping:
                # First time seeing this cert file - mount it
                container_cert_path = f"/tmp/{os.path.basename(cert_path)}"
                container_args.extend(["-v", f"{cert_path}:{container_cert_path}:ro"])
                cert_mapping[cert_path] = container_cert_path
                mounted_paths.add(cert_path)

            # Always set the environment variable to point to the container path
            container_args.extend(["-e", f"{env_var}={cert_mapping[cert_path]}"])

    # Mount SSL_CERT_DIR if set and is a directory
    ssl_cert_dir_env = os.environ.get("SSL_CERT_DIR")
    if ssl_cert_dir_env and os.path.isdir(ssl_cert_dir_env):
        container_cert_dir = "/tmp/ssl-cert-dir"
        container_args.extend(["-v", f"{ssl_cert_dir_env}:{container_cert_dir}:ro"])
        container_args.extend(["-e", f"SSL_CERT_DIR={container_cert_dir}"])
        mounted_paths.add(ssl_cert_dir_env)

    # Add environment variables for network restrictions (must be before image)
    if sandbox_args.restrict_network:
        container_args.extend(["-e", "PATCHPAL_ENABLE_WEB=false"])
        container_args.extend(["-e", "PATCHPAL_ENABLE_MCP=false"])
        container_args.extend(["-e", "LITELLM_LOCAL_MODEL_COST_MAP=True"])
        container_args.extend(["-e", "PYTHONUNBUFFERED=1"])
        container_args.extend(["-e", "TIKTOKEN_CACHE_DIR=/tmp/tiktoken_cache"])

    # Add image
    container_args.append(sandbox_args.image)

    # If --shell flag is set, just run bash and return early
    if sandbox_args.shell:
        # Extract --model from patchpal args if provided and set as PATCHPAL_MODEL env var
        if patchpal_args:
            i = 0
            while i < len(patchpal_args):
                if patchpal_args[i] == "--model" and i + 1 < len(patchpal_args):
                    model = patchpal_args[i + 1]
                    # Insert env var before image
                    image_index = len(container_args) - 1
                    container_args.insert(image_index, f"PATCHPAL_MODEL={model}")
                    container_args.insert(image_index, "-e")
                    break
                i += 1
        container_args.append("bash")
        return container_args, runtime

    # Build patchpal command
    patchpal_cmd = "patchpal"
    patchpal_cmd_args = list(patchpal_args)

    if patchpal_args and patchpal_args[0] in ["autopilot", "patchpal-autopilot"]:
        patchpal_cmd = "patchpal-autopilot"
        patchpal_cmd_args = patchpal_args[1:]  # Remove subcommand

    # For network restrictions, extract model and pass as env var (matching launch-agent-sandbox)
    if sandbox_args.restrict_network:
        model_arg = None
        i = 0
        while i < len(patchpal_cmd_args):
            if patchpal_cmd_args[i] == "--model" and i + 1 < len(patchpal_cmd_args):
                model_arg = patchpal_cmd_args[i + 1]
                break
            i += 1

        # Pass model and AWS-related env vars (must add before image, so go back and insert)
        if model_arg:
            # Find where image was added and insert env vars before it
            image_index = len(container_args) - 1
            container_args.insert(image_index, f"MODEL={model_arg}")
            container_args.insert(image_index, "-e")

            # Also set AWS_BEDROCK_ENDPOINT if we have it
            bedrock_endpoint = os.environ.get("AWS_BEDROCK_ENDPOINT") or os.environ.get(
                "AWS_ENDPOINT_URL_BEDROCK_RUNTIME"
            )
            if bedrock_endpoint:
                container_args.insert(image_index, f"AWS_BEDROCK_ENDPOINT={bedrock_endpoint}")
                container_args.insert(image_index, "-e")

    # Build the shell command
    shell_cmd_parts = []

    if dev_mode:
        # Development mode: reinstall patchpal from mounted source
        # Show pip output in case of errors, but suppress normal installation messages
        shell_cmd_parts.append("pip install -e /patchpal-dev 2>&1 | grep -i error || true")
    elif "patchpal-sandbox" in sandbox_args.image:
        # Using pre-built image, skip pip install
        pass
    else:
        # Custom image, install patchpal from PyPI
        shell_cmd_parts.append("pip install -q patchpal")

    # Add network restriction script if enabled
    if sandbox_args.restrict_network:
        restriction_script = build_network_restriction_script(
            sandbox_args.allow_url, sandbox_args.test_restrictions
        )
        shell_cmd_parts.append(restriction_script)

        # If test mode, exit after testing
        if sandbox_args.test_restrictions:
            shell_cmd = "\n".join(shell_cmd_parts)  # Use newline for multi-line scripts
            container_args.extend(["bash", "-c", shell_cmd])
            return container_args, runtime

    # Add main patchpal command
    if sandbox_args.restrict_network:
        # Use launch-agent-sandbox pattern: model from env var
        shell_cmd_parts.append(f"""
echo ""
echo "=== Starting PatchPal ==="
echo "Model: $MODEL"
echo ""
exec {patchpal_cmd} --model "$MODEL"
""")
    else:
        # Normal mode: use $@ to pass all arguments
        shell_cmd_parts.append(f"""
echo ""
echo "=== Starting PatchPal ==="
echo "Model: {model_name if model_name else "default"}"
echo ""
exec {patchpal_cmd} "$@"
""")

    # Join all commands in a single bash script with proper line endings
    # Add set -e at the beginning to exit on any error
    shell_cmd = "set -e\n" + "\n".join(shell_cmd_parts)

    # Pass arguments differently based on network restrictions
    if sandbox_args.restrict_network:
        # With restrictions: model passed as env var, no additional args needed
        container_args.extend(["bash", "-c", shell_cmd])
    else:
        # Without restrictions: pass args after -- separator
        container_args.extend(["bash", "-c", shell_cmd, "--"] + patchpal_cmd_args)

    return container_args, runtime


def show_help():
    """Show help message."""
    help_text = """
sandbox-patchpal - Run PatchPal in an isolated container

USAGE:
    patchpal-sandbox [SCRIPT_OPTIONS] -- [PATCHPAL_ARGS...]

    Note: Script options must come BEFORE the '--' separator.
          PatchPal options must come AFTER the '--' separator.

DESCRIPTION:
    Runs PatchPal inside a Docker/Podman container with:
    - Network access (required for cloud LLMs like OpenAI, Anthropic)
    - No resource limits by default (uses Docker/Podman defaults)
    - Current directory mounted as /workspace
    - Pre-built image with patchpal installed (fast startup)
    - Auto-mounts ~/.patchpal for custom tools, config, and memory
    - Custom tools work automatically (from ~/.patchpal/tools/ and <repo>/.patchpal/tools/)
    - Auto-sets OLLAMA_CONTEXT_LENGTH for Ollama models:
      * 8192 for regular models (agents)
      * 32768 for reasoning models (gpt-oss, deepseek-r1, qwq, qwen)

    Recommended for autopilot mode and high-risk operations.

SCRIPT OPTIONS:
    --image IMAGE       Container image to use (default: ghcr.io/amaiya/patchpal-sandbox:latest)
                        Use python:3.11-slim to get latest patchpal from PyPI (slower startup)
    --no-network        Disable network access (incompatible with cloud LLMs)
    --host-network      Use host network (for local Ollama/vLLM servers on localhost)
    --memory LIMIT      Memory limit (e.g., 2g, 4g) - optional, no limit by default
    --cpus NUM          CPU limit (e.g., 2, 4) - optional, no limit by default
    --env-file FILE     Load environment variables from .env file
    --restrict-network  Enable iptables firewall for network isolation
                        Automatically detects LLM endpoints from environment variables:
                        * OpenAI (OPENAI_API_KEY)
                        * Anthropic (ANTHROPIC_API_KEY)
                        * AWS Bedrock (AWS_REGION + AWS_ACCESS_KEY_ID)
                        * Azure OpenAI (AZURE_OPENAI_KEY + AZURE_OPENAI_RESOURCE)
                        * Google AI (GOOGLE_API_KEY)
                        * Groq, Cohere, Together, Replicate, etc.
                        Custom endpoints also detected from *_BASE_URL env vars
    --allow-url URL     Allow network access to specific URL (can be specified multiple times)
                        Used with --restrict-network to add additional URLs beyond auto-detected
                        Example:
                          --allow-url https://pypi.org (for pip install)
                          --allow-url https://github.com (for git operations)
    --test-restrictions Test network restrictions and exit (requires --restrict-network)
    --shell             Drop into bash shell instead of running patchpal (for debugging)
                        If --model is provided after --, sets PATCHPAL_MODEL env var automatically
    -h, --help          Show this help message

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
    - All OLLAMA_* variables (e.g., OLLAMA_CONTEXT_LENGTH - auto-set if not specified)
    - SSL_CERT_FILE and REQUESTS_CA_BUNDLE (auto-mounted if paths exist)

    You can load these from a .env file using --env-file:

    Example .env file:
        # API Keys
        OPENAI_API_KEY=sk-your-key-here
        ANTHROPIC_API_KEY=sk-ant-your-key-here

        # Custom endpoints (optional)
        OPENAI_BASE_URL=https://your-proxy.com/v1

        # Optional: Disable permissions for interactive mode
        # (Not needed for autopilot - it disables permissions automatically)
        # PATCHPAL_REQUIRE_PERMISSION=false

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
    - Permissions behavior:
      * Interactive mode (default): Permissions ENABLED (prompts before operations)
      * Autopilot mode: Permissions DISABLED automatically (autonomous operation)

    NETWORK RESTRICTIONS (--restrict-network):
      When enabled, uses iptables firewall to enforce network isolation:

      AUTO-DETECTION:
      * Automatically detects LLM provider APIs from environment variables
      * Detects standard providers: OpenAI, Anthropic, Google, Groq, Cohere, etc.
      * Detects custom endpoints from *_BASE_URL environment variables
      * Detects AWS Bedrock from AWS_REGION (standard or GovCloud)
      * Detects Azure OpenAI from AZURE_OPENAI_RESOURCE
      * No need to manually specify --allow-url for detected providers

      FIREWALL RULES:
      - Only allowed URLs are accessible (auto-detected + --allow-url)
      - DNS resolution permitted (required for hostname lookup)
      - Localhost accessible (127.0.0.1/8)
      - All other network traffic BLOCKED and LOGGED
      - Web tools and MCP automatically disabled
      - Ideal for sensitive/regulated environments

      Use cases:
      * Compliance: Meet data governance requirements
      * Security: Prevent data exfiltration
      * Testing: Verify network isolation works correctly

      Example auto-detected endpoints:
      * OPENAI_API_KEY → https://api.openai.com
      * ANTHROPIC_API_KEY → https://api.anthropic.com
      * AWS_REGION=us-gov-west-1 → https://bedrock-runtime-fips.us-gov-west-1.amazonaws.com
      * AZURE_OPENAI_RESOURCE=myresource → https://myresource.openai.azure.com

      Example additional URLs (use --allow-url):
      * Package repos: https://pypi.org, https://files.pythonhosted.org
      * Code repos: https://github.com, https://api.github.com

      Blocked connections are logged via iptables for audit purposes.

NOTES:
    - Default image (ghcr.io/amaiya/patchpal-sandbox:latest) has patchpal pre-installed for fast startup
    - First run downloads the image (~150MB, one-time)
    - Subsequent runs start instantly (no pip install needed)
    - For latest patchpal from PyPI use: --image python:3.11-slim (slower, ~10-30s pip install)
    - Current directory mounted at /workspace (read-write)
    - ~/.patchpal mounted at /root/.patchpal if it exists
    - SSL certificates auto-mounted from /etc/ssl/certs if present
    - Files in /workspace persist on host, other files are lost on exit
    - Container ~ = /root (not your host home directory)
    - Use --no-network for maximum isolation with local models only
    - For Ollama on Windows with WSL: Enable mirrored networking in .wslconfig
      (Add networkingMode=mirrored under [wsl2] to use localhost)

CORPORATE NETWORKS (Linux/WSL):
    If you get SSL certificate errors behind a corporate proxy/firewall:

    1. Ensure your custom CA cert is in /etc/ssl/certs/ca-certificates.crt
       (The script auto-mounts this if it exists on Linux/WSL)

    2. Or set environment variables pointing to your cert:
       export SSL_CERT_FILE=/path/to/your/ca-bundle.crt
       patchpal-sandbox -- --model openai/gpt-5.2-codex

    On macOS/Windows: Docker Desktop handles certificates differently.
    You may need to add certificates to Docker Desktop's trusted CAs.

EXAMPLES:

    # Interactive mode - permissions ENABLED (prompts before operations)
    patchpal-sandbox -- --model anthropic/claude-sonnet-4-5

    # Interactive mode - load API keys from .env file
    patchpal-sandbox --env-file .env -- --model openai/gpt-5.2-codex
    patchpal-sandbox --env-file ~/.config/patchpal/.env -- --model anthropic/claude-sonnet-4-5

    # AutoPilot mode - permissions automatically DISABLED
    patchpal-sandbox  -- autopilot --model openai/gpt-5-mini --prompt "Add error handling to auth.py"

    # AutoPilot mode - read file containing prompt and and .env file
    patchpal-sandbox --env-file .env -- autopilot --model openai/gpt-5.2-codex --prompt-file task.md

    # Network Restrictions: Auto-detect LLM API from environment
    # (Automatically allows OpenAI API if OPENAI_API_KEY is set)
    patchpal-sandbox --restrict-network --env-file .env \
      -- --model openai/gpt-5.2-codex

    # Network Restrictions: Auto-detect + additional URLs
    # (Automatically allows Anthropic API + adds PyPI for pip install)
    patchpal-sandbox --restrict-network \
      --allow-url https://pypi.org \
      --allow-url https://files.pythonhosted.org \
      --env-file .env \
      -- --model anthropic/claude-sonnet-4-5

    # Network Restrictions: Manual URLs only (no auto-detection needed)
    patchpal-sandbox --restrict-network \
      --allow-url https://api.openai.com \
      --allow-url https://api.anthropic.com \
      -- autopilot --model openai/gpt-5.2-codex --prompt "Fix the bug"

    # Network Restrictions: AWS Bedrock (auto-detected from AWS_REGION)
    patchpal-sandbox --restrict-network --env-file .env.govcloud \
      -- --model bedrock/us.anthropic.claude-3-5-sonnet-20241022-v2:0

    # Test network restrictions (verify auto-detection and firewall)
    patchpal-sandbox --restrict-network --env-file .env --test-restrictions

    # Ollama: Linux/WSL requires host network to reach Ollama on localhost
    patchpal-sandbox --host-network -- --model ollama_chat/qwen3:8b # interactive
    patchpal-sandbox --host-network -- autopilot --model ollama_chat/qwen3:8b # autopilot

    # Ollama: Windows/macOS requires setting OLLAMA_API_BASE
    # Docker: export OLLAMA_API_BASE=http://host.docker.internal:11434
    # PodMan: export OLLAMA_API_BASE=http://host.containers.internal:11434
    patchpal-sandbox --host-network -- --model ollama_chat/qwen3:8b

    # Debugging: Drop into shell inside container
    patchpal-sandbox --env-file .env --shell

    # Debugging: Drop into shell with model pre-configured
    patchpal-sandbox --env-file .env --shell -- --model anthropic/claude-sonnet-4-5
    # Inside container: just run 'patchpal' (uses PATCHPAL_MODEL automatically)


SEE ALSO:
    - docs/usage/autopilot.md - Autopilot safety guidelines
    - docs/safety.md - General safety and security considerations
"""
    print(help_text)


def main():
    """Entry point for patchpal-sandbox command."""

    # Check for help first (before parsing anything)
    if "-h" in sys.argv or "--help" in sys.argv:
        show_help()
        sys.exit(0)

    # Parse arguments (everything before -- is for sandbox, everything after is for patchpal)
    try:
        separator_idx = sys.argv.index("--")
        sandbox_argv = sys.argv[1:separator_idx]
        patchpal_argv = sys.argv[separator_idx + 1 :]
    except ValueError:
        # No separator found - all args are for sandbox
        sandbox_argv = sys.argv[1:]
        patchpal_argv = []

    # If no arguments at all, show help
    if not sandbox_argv and not patchpal_argv:
        show_help()
        sys.exit(0)

    # Parse sandbox arguments
    parser = argparse.ArgumentParser(add_help=False)  # We handle help manually
    parser.add_argument("--image", default="ghcr.io/amaiya/patchpal-sandbox:latest")
    parser.add_argument("--network", default="bridge")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--host-network", action="store_true")
    parser.add_argument("--memory", default=None)
    parser.add_argument("--cpus", type=float, default=None)
    parser.add_argument("--env-file", default=None)
    parser.add_argument(
        "--dev",
        action="store_true",
        help="Mount local patchpal code for development (requires being run from patchpal repo root)",
    )
    # Network restriction options
    parser.add_argument(
        "--restrict-network",
        action="store_true",
        help="Enable iptables firewall to restrict network access (use with --allow-url)",
    )
    parser.add_argument(
        "--allow-url",
        action="append",
        default=[],
        help="Allow network access to specific URL (can be specified multiple times, requires --restrict-network)",
    )
    parser.add_argument(
        "--test-restrictions",
        action="store_true",
        help="Test network restrictions and exit (requires --restrict-network)",
    )
    parser.add_argument(
        "--shell",
        action="store_true",
        help="Drop into bash shell instead of running patchpal (for debugging)",
    )

    try:
        sandbox_args = parser.parse_args(sandbox_argv)
    except SystemExit:
        show_help()
        sys.exit(1)

    # Validate network restriction arguments
    if sandbox_args.test_restrictions and not sandbox_args.restrict_network:
        print("❌ Error: --test-restrictions requires --restrict-network", file=sys.stderr)
        sys.exit(1)

    if sandbox_args.allow_url and not sandbox_args.restrict_network:
        print("⚠️  Warning: --allow-url has no effect without --restrict-network", file=sys.stderr)

    # Handle network flags
    if sandbox_args.no_network:
        sandbox_args.network = "none"
    elif sandbox_args.host_network:
        sandbox_args.network = "host"

    # Load .env file if specified
    if sandbox_args.env_file:
        print(f"Loading environment variables from: {sandbox_args.env_file}")
        load_env_file(sandbox_args.env_file)

    # Auto-detect LLM endpoints if network restrictions are enabled
    detected_endpoints = []
    if sandbox_args.restrict_network:
        detected_endpoints = detect_llm_endpoints_from_env()
        if detected_endpoints:
            print("\n🔍 Auto-detected LLM endpoints from environment:")
            for url in detected_endpoints:
                print(f"   - {url}")
            print()

        # Combine user-specified and auto-detected URLs
        all_allowed_urls = list(sandbox_args.allow_url) + detected_endpoints
        # Deduplicate
        all_allowed_urls = list(dict.fromkeys(all_allowed_urls))  # Preserves order
        sandbox_args.allow_url = all_allowed_urls

        # Update warning if still no URLs
        if not sandbox_args.allow_url:
            print(
                "⚠️  Warning: --restrict-network enabled but no LLM endpoints detected",
                file=sys.stderr,
            )
            print("    Set API keys (e.g., OPENAI_API_KEY) or use --allow-url", file=sys.stderr)
            print(
                "    All external network access will be blocked (DNS and localhost only)",
                file=sys.stderr,
            )

    # Build container command
    container_args, runtime = build_container_args(sandbox_args, patchpal_argv)

    # Show what we're doing
    print(f"Using container runtime: {runtime}")
    print(f"Image: {sandbox_args.image}")
    print(f"Network: {sandbox_args.network}")
    print(f"Workspace: {os.getcwd()}")

    # Show network restriction settings
    if sandbox_args.restrict_network:
        print("\n🔒 Network Restrictions: ENABLED")
        if sandbox_args.allow_url:
            # Separate auto-detected from manually specified
            auto_detected_set = set(detected_endpoints)

            print("   Allowed URLs:")
            for url in sandbox_args.allow_url:
                if url in auto_detected_set:
                    print(f"     - {url} (auto-detected)")
                else:
                    print(f"     - {url}")
        else:
            print("   Allowed URLs: NONE (only DNS and localhost)")

        if sandbox_args.test_restrictions:
            print("   Mode: TEST (will validate restrictions and exit)")
        else:
            print("   Mode: ENFORCED (iptables firewall active)")
        print("   Web tools: DISABLED")
        print("   MCP tools: DISABLED")

    # Debug: Show SSL cert files being mounted (if any)
    ssl_env_vars = {
        k: v for k, v in os.environ.items() if "SSL" in k or "CERT" in k or "CA_BUNDLE" in k
    }
    if ssl_env_vars and sandbox_args.dev:
        print("\n🔒 SSL environment variables (dev mode debug):")
        for k, v in ssl_env_vars.items():
            print(f"  {k}={v}")

    print()

    # Run container
    try:
        result = subprocess.run(container_args, check=False)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user (Ctrl-C)", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error running container: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
