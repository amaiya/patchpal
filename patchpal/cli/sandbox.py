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

    # Mount SSL_CERT_FILE and REQUESTS_CA_BUNDLE if set
    # Map host cert files to /tmp inside container since parent dirs may not exist
    cert_mapping = {}  # Track host path -> container path mappings
    for env_var in ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"]:
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

    # Add image
    container_args.append(sandbox_args.image)

    # Build patchpal command
    patchpal_cmd = "patchpal"
    patchpal_cmd_args = list(patchpal_args)

    if patchpal_args and patchpal_args[0] in ["autopilot", "patchpal-autopilot"]:
        patchpal_cmd = "patchpal-autopilot"
        patchpal_cmd_args = patchpal_args[1:]  # Remove subcommand

    # Build shell command with proper quoting
    import shlex

    quoted_args = " ".join(shlex.quote(arg) for arg in patchpal_cmd_args)

    # Build the shell command
    if dev_mode:
        # Development mode: reinstall patchpal from mounted source
        # Show pip output in case of errors, but suppress normal installation messages
        shell_cmd = f"pip install -e /patchpal-dev 2>&1 | grep -i error || true && {patchpal_cmd} {quoted_args}"
    elif "patchpal-sandbox" in sandbox_args.image:
        # Using pre-built image, skip pip install
        shell_cmd = f"{patchpal_cmd} {quoted_args}"
    else:
        # Custom image, install patchpal from PyPI
        shell_cmd = f"pip install -q patchpal && {patchpal_cmd} {quoted_args}"

    container_args.extend(["bash", "-c", shell_cmd])

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

    # Ollama: Linux/WSL requires host network to reach Ollama on localhost
    patchpal-sandbox --host-network -- --model ollama_chat/qwen3:8b # interactive
    patchpal-sandbox --host-network -- autopilot --model ollama_chat/qwen3:8b # autopilot

    # Ollama: Windows/macOS requires setting OLLAMA_API_BASE
    # Docker: export OLLAMA_API_BASE=http://host.docker.internal:11434
    # PodMan: export OLLAMA_API_BASE=http://host.containers.internal:11434
    patchpal-sandbox --host-network -- --model ollama_chat/qwen3:8b


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

    try:
        sandbox_args = parser.parse_args(sandbox_argv)
    except SystemExit:
        show_help()
        sys.exit(1)

    # Handle network flags
    if sandbox_args.no_network:
        sandbox_args.network = "none"
    elif sandbox_args.host_network:
        sandbox_args.network = "host"

    # Load .env file if specified
    if sandbox_args.env_file:
        print(f"Loading environment variables from: {sandbox_args.env_file}")
        load_env_file(sandbox_args.env_file)

    # Build container command
    container_args, runtime = build_container_args(sandbox_args, patchpal_argv)

    # Show what we're doing
    print(f"Using container runtime: {runtime}")
    print(f"Image: {sandbox_args.image}")
    print(f"Network: {sandbox_args.network}")
    print(f"Workspace: {os.getcwd()}")

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
