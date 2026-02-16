#!/usr/bin/env python3
"""CLI commands for managing MCP servers.

Provides commands to add, remove, list, and manage MCP server configurations.

Usage:
    patchpal-mcp add <name> <url> [options]
    patchpal-mcp list
    patchpal-mcp get <name>
    patchpal-mcp remove <name>
    patchpal-mcp test <name>
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from patchpal.tools.mcp import (
    is_mcp_available,
    list_mcp_prompts,
    list_mcp_resources,
    load_mcp_tools,
)


def _get_config_path(scope: str = "user") -> Path:
    """Get the configuration file path based on scope.

    Args:
        scope: Configuration scope - "user", "project", or "local"

    Returns:
        Path to mcp-config.json file
    """
    if scope == "user":
        # User-wide config
        config_dir = Path.home() / ".patchpal"
        config_dir.mkdir(exist_ok=True)
        return config_dir / "mcp-config.json"
    elif scope in ("project", "local"):
        # Project-specific config
        config_dir = Path(".patchpal")
        config_dir.mkdir(exist_ok=True)
        return config_dir / "mcp-config.json"
    else:
        raise ValueError(f"Invalid scope: {scope}. Must be 'user', 'project', or 'local'")


def _load_config(config_path: Path) -> Dict[str, Any]:
    """Load configuration from file."""
    if not config_path.exists():
        return {"mcp": {}}

    try:
        with open(config_path) as f:
            config = json.load(f)
            if "mcp" not in config:
                config["mcp"] = {}
            return config
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in config file: {e}")
        sys.exit(1)


def _save_config(config: Dict[str, Any], config_path: Path):
    """Save configuration to file."""
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)
    print(f"✓ Configuration saved to {config_path}")


def cmd_add(args):
    """Add a new MCP server."""
    config_path = _get_config_path(args.scope)
    config = _load_config(config_path)

    # Check if server already exists
    if args.name in config["mcp"]:
        if not args.force:
            print(f"Error: Server '{args.name}' already exists.")
            print("Use --force to overwrite or choose a different name.")
            sys.exit(1)
        print(f"Overwriting existing server '{args.name}'")

    # Build server configuration
    server_config = {
        "enabled": not args.disabled,
    }

    # Determine transport type and set appropriate fields
    if args.transport in ("http", "sse"):
        server_config["type"] = "remote"
        server_config["url"] = args.url_or_command

        # Add headers if provided
        if args.header:
            server_config["headers"] = {}
            for header in args.header:
                if ":" not in header:
                    print(f"Error: Invalid header format '{header}'. Use 'Name: Value' format.")
                    sys.exit(1)
                name, value = header.split(":", 1)
                server_config["headers"][name.strip()] = value.strip()

    elif args.transport == "stdio":
        server_config["type"] = "local"

        # Parse command - everything after the name is the command
        if not args.command_args:
            print("Error: stdio transport requires a command.")
            print("Usage: patchpal-mcp add --transport stdio <name> -- <command> [args...]")
            sys.exit(1)

        server_config["command"] = args.command_args

        # Add environment variables if provided
        if args.env:
            server_config["environment"] = {}
            for env_var in args.env:
                if "=" not in env_var:
                    print(
                        f"Error: Invalid environment variable format '{env_var}'. Use 'KEY=value' format."
                    )
                    sys.exit(1)
                key, value = env_var.split("=", 1)
                server_config["environment"][key] = value
        else:
            server_config["environment"] = {}

    # Add description if provided
    if args.description:
        server_config["description"] = args.description

    # Add to config
    config["mcp"][args.name] = server_config

    # Save config
    _save_config(config, config_path)
    print(f"✓ Added MCP server '{args.name}' ({args.transport} transport)")


def cmd_list(args):
    """List all configured MCP servers."""
    config_path = _get_config_path(args.scope)
    config = _load_config(config_path)

    if not config["mcp"]:
        print("No MCP servers configured.")
        print(f"Configuration file: {config_path}")
        return

    print(f"MCP Servers (from {config_path}):")
    print("=" * 60)

    for name, server_config in config["mcp"].items():
        enabled = "✓" if server_config.get("enabled", True) else "✗"
        server_type = server_config.get("type", "local")

        print(f"\n{enabled} {name} ({server_type})")

        if server_type == "remote":
            print(f"  URL: {server_config.get('url', 'N/A')}")
            if server_config.get("headers"):
                print(f"  Headers: {list(server_config['headers'].keys())}")
        else:
            command = server_config.get("command", [])
            if command:
                print(f"  Command: {' '.join(command)}")
            if server_config.get("environment"):
                print(f"  Environment: {list(server_config['environment'].keys())}")

        if server_config.get("description"):
            print(f"  Description: {server_config['description']}")


def cmd_get(args):
    """Get details about a specific MCP server."""
    config_path = _get_config_path(args.scope)
    config = _load_config(config_path)

    if args.name not in config["mcp"]:
        print(f"Error: Server '{args.name}' not found.")
        print("Use 'patchpal-mcp list' to see all configured servers.")
        sys.exit(1)

    server_config = config["mcp"][args.name]

    print(f"MCP Server: {args.name}")
    print("=" * 60)
    print(json.dumps(server_config, indent=2))


def cmd_remove(args):
    """Remove an MCP server."""
    config_path = _get_config_path(args.scope)
    config = _load_config(config_path)

    if args.name not in config["mcp"]:
        print(f"Error: Server '{args.name}' not found.")
        sys.exit(1)

    # Remove server
    del config["mcp"][args.name]

    # Save config
    _save_config(config, config_path)
    print(f"✓ Removed MCP server '{args.name}'")


def cmd_test(args):
    """Test connection to an MCP server."""
    if not is_mcp_available():
        print("Error: MCP SDK not installed.")
        print("Install it with: pip install patchpal[mcp]")
        sys.exit(1)

    config_path = _get_config_path(args.scope)
    config = _load_config(config_path)

    if args.name not in config["mcp"]:
        print(f"Error: Server '{args.name}' not found.")
        sys.exit(1)

    print(f"Testing MCP server '{args.name}'...")
    print("=" * 60)

    try:
        # Load tools from this server
        print("Loading tools...")
        tools, functions = load_mcp_tools(config_path)

        # Filter tools from this server
        server_tools = [t for t in tools if t["function"]["name"].startswith(f"{args.name}_")]

        print("✓ Connected successfully!")
        print(f"  Found {len(server_tools)} tools")

        if server_tools:
            print("\nAvailable tools:")
            for tool in server_tools[:10]:  # Show first 10
                name = tool["function"]["name"]
                desc = tool["function"].get("description", "")
                print(f"  • {name}")
                if desc:
                    # Truncate long descriptions
                    if len(desc) > 80:
                        desc = desc[:77] + "..."
                    print(f"    {desc}")

            if len(server_tools) > 10:
                print(f"  ... and {len(server_tools) - 10} more")

        # Try to list resources
        print("\nListing resources...")
        resources = list_mcp_resources()
        server_resources = [r for r in resources if r["server"] == args.name]
        print(f"  Found {len(server_resources)} resources")

        # Try to list prompts
        print("\nListing prompts...")
        prompts = list_mcp_prompts()
        server_prompts = [p for p in prompts if p["server"] == args.name]
        print(f"  Found {len(server_prompts)} prompts")

        print("\n✓ Test successful!")

    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        sys.exit(1)


def main():
    """Main entry point for MCP CLI commands."""
    parser = argparse.ArgumentParser(
        prog="patchpal-mcp",
        description="Manage Model Context Protocol (MCP) servers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Add a remote HTTP server
  patchpal-mcp add github --transport http https://api.githubcopilot.com/mcp/

  # Add a remote server with authentication
  patchpal-mcp add sentry --transport http https://mcp.sentry.dev/mcp \\
    --header "Authorization: Bearer \\${SENTRY_TOKEN}"

  # Add a local stdio server
  patchpal-mcp add filesystem --transport stdio -- \\
    npx -y @modelcontextprotocol/server-filesystem /path/to/dir

  # Add with environment variables
  patchpal-mcp add db --transport stdio \\
    --env DB_HOST=localhost --env DB_PASSWORD=\\${DB_PASS} -- \\
    npx -y @bytebase/dbhub

  # List all servers
  patchpal-mcp list

  # Get server details
  patchpal-mcp get github

  # Test server connection
  patchpal-mcp test github

  # Remove a server
  patchpal-mcp remove github

Scope:
  --scope user     : ~/.patchpal/mcp-config.json (global config for all projects)
  --scope project  : .patchpal/mcp-config.json (project-specific, shared via git)
  --scope local    : .patchpal/mcp-config.json (same as project)

Note: When both global and project configs exist, they are merged with project
servers overriding global servers by name. This allows you to:
- Define commonly-used servers globally
- Override or disable them per-project
- Add project-specific servers
        """,
    )

    # Global options
    parser.add_argument(
        "--scope",
        choices=["user", "project", "local"],
        default="user",
        help="Configuration scope (default: user)",
    )

    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new MCP server")
    add_parser.add_argument("name", help="Server name")
    add_parser.add_argument(
        "url_or_command",
        nargs="?",
        help="Server URL (for http/sse) or unused (for stdio with --)",
    )
    add_parser.add_argument(
        "--transport",
        choices=["http", "sse", "stdio"],
        default="http",
        help="Transport type (default: http)",
    )
    add_parser.add_argument(
        "--header",
        action="append",
        help="HTTP header (format: 'Name: Value'). Can be specified multiple times.",
    )
    add_parser.add_argument(
        "--env",
        action="append",
        help="Environment variable (format: 'KEY=value'). Can be specified multiple times.",
    )
    add_parser.add_argument(
        "--description",
        help="Server description",
    )
    add_parser.add_argument(
        "--disabled",
        action="store_true",
        help="Add server in disabled state",
    )
    add_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing server with same name",
    )
    add_parser.add_argument(
        "command_args",
        nargs="*",
        help="Command and arguments for stdio transport (use after --)",
    )

    # List command
    subparsers.add_parser("list", help="List all configured MCP servers")

    # Get command
    get_parser = subparsers.add_parser("get", help="Get details about an MCP server")
    get_parser.add_argument("name", help="Server name")

    # Remove command
    remove_parser = subparsers.add_parser("remove", help="Remove an MCP server")
    remove_parser.add_argument("name", help="Server name")

    # Test command
    test_parser = subparsers.add_parser("test", help="Test connection to an MCP server")
    test_parser.add_argument("name", help="Server name")

    # Parse arguments
    args = parser.parse_args()

    # Execute command
    if args.command == "add":
        cmd_add(args)
    elif args.command == "list":
        cmd_list(args)
    elif args.command == "get":
        cmd_get(args)
    elif args.command == "remove":
        cmd_remove(args)
    elif args.command == "test":
        cmd_test(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
