#!/usr/bin/env python3
"""
PatchPal Sandbox - Run PatchPal in isolated Docker/Podman container

Provides sandboxed execution for both interactive and autopilot modes.

Usage:
    patchpal-sandbox --model openai/gpt-5.2-codex
    patchpal-sandbox --env-file .env -- autopilot --prompt "Fix the bug" --completion-promise "DONE"
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

    # Track mounted paths to avoid duplicates
    mounted_paths = set()

    # Mount ~/.patchpal if it exists
    patchpal_dir = os.path.expanduser("~/.patchpal")
    if os.path.isdir(patchpal_dir):
        container_args.extend(["-v", f"{patchpal_dir}:/root/.patchpal"])
        mounted_paths.add(patchpal_dir)

    # Mount SSL certificates if they exist (Linux/WSL)
    ssl_cert_file = "/etc/ssl/certs/ca-certificates.crt"
    if os.path.isfile(ssl_cert_file):
        container_args.extend(["-v", f"{ssl_cert_file}:{ssl_cert_file}:ro"])
        mounted_paths.add(ssl_cert_file)

    ssl_cert_dir = "/usr/local/share/ca-certificates"
    if os.path.isdir(ssl_cert_dir) and os.listdir(ssl_cert_dir):
        container_args.extend(["-v", f"{ssl_cert_dir}:{ssl_cert_dir}:ro"])
        mounted_paths.add(ssl_cert_dir)

    # Mount SSL_CERT_FILE and REQUESTS_CA_BUNDLE if set
    for env_var in ["SSL_CERT_FILE", "REQUESTS_CA_BUNDLE"]:
        cert_path = os.environ.get(env_var)
        if cert_path and os.path.isfile(cert_path) and cert_path not in mounted_paths:
            container_args.extend(["-v", f"{cert_path}:{cert_path}:ro"])
            container_args.extend(["-e", f"{env_var}={cert_path}"])
            mounted_paths.add(cert_path)

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
       patchpal-sandbox -- --model openai/gpt-5.2-codex

    On macOS/Windows: Docker Desktop handles certificates differently.
    You may need to add certificates to Docker Desktop's trusted CAs.

EXAMPLES:
    # Load API keys from .env file
    patchpal-sandbox --env-file .env -- --model openai/gpt-5.2-codex
    patchpal-sandbox --env-file ~/.config/patchpal/.env -- --model anthropic/claude-sonnet-4-5

    # Interactive mode with cloud LLM (network enabled by default)
    patchpal-sandbox -- --model anthropic/claude-sonnet-4-5

    # With local model (Ollama) - requires host network to reach Ollama on localhost
    patchpal-sandbox --host-network -- --model ollama_chat/llama3.1

    # Run AUTOPILOT mode (non-interactive, permissions automatically disabled)
    patchpal-sandbox --env-file .env -- autopilot --model openai/gpt-5.2-codex --prompt "Add error handling to auth.py. Output: <promise>COMPLETE</promise> when done." --completion-promise "COMPLETE"

    # AUTOPILOT with prompt from file
    patchpal-sandbox --env-file .env -- autopilot --model openai/gpt-5.2-codex --prompt-file task.md --completion-promise "DONE"


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
    parser.add_argument("--image", default="python:3.11-slim")
    parser.add_argument("--network", default="bridge")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--host-network", action="store_true")
    parser.add_argument("--memory", default=None)
    parser.add_argument("--cpus", type=float, default=None)
    parser.add_argument("--env-file", default=None)

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
