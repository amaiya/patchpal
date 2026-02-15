#!/usr/bin/env python3
"""Demo script showing MCP resources and prompts discovery.

This script demonstrates how to list and access MCP resources
and prompts from connected servers.

Usage:
    python examples/mcp/demo_resources_prompts.py
"""

import sys
from pathlib import Path

# Add patchpal to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from patchpal.tools.mcp import (
    is_mcp_available,
    list_mcp_prompts,
    list_mcp_resources,
    load_mcp_tools,
    read_mcp_resource,
)


def main():
    """Demonstrate MCP resources and prompts discovery."""
    print("MCP Resources and Prompts Demo")
    print("=" * 60)

    # Check if MCP is available
    if not is_mcp_available():
        print("\n❌ MCP SDK not installed")
        print("Install it with: pip install patchpal[mcp]")
        return 1

    print("\n✓ MCP SDK is available\n")

    # Load MCP tools first (this populates the server configs cache)
    print("Loading MCP tools...")
    tools, functions = load_mcp_tools()
    print(f"  Loaded {len(tools)} tools from MCP servers\n")

    if not tools:
        print("No MCP servers configured or enabled.")
        print("See examples/mcp/config.example.json for configuration examples.")
        return 0

    # List available resources
    print("=" * 60)
    print("Available MCP Resources:")
    print("=" * 60)
    resources = list_mcp_resources()

    if resources:
        for resource in resources:
            print(f"\n  Server: {resource['server']}")
            print(f"  URI:    {resource['uri']}")
            if resource.get("name"):
                print(f"  Name:   {resource['name']}")
            if resource.get("description"):
                print(f"  Desc:   {resource['description']}")
            if resource.get("mimeType"):
                print(f"  Type:   {resource['mimeType']}")
    else:
        print("\n  No resources available from configured MCP servers.")

    # List available prompts
    print("\n" + "=" * 60)
    print("Available MCP Prompts:")
    print("=" * 60)
    prompts = list_mcp_prompts()

    if prompts:
        for prompt in prompts:
            print(f"\n  Server: {prompt['server']}")
            print(f"  Name:   {prompt['name']}")
            if prompt.get("description"):
                print(f"  Desc:   {prompt['description']}")

            if prompt.get("arguments"):
                print("  Args:")
                for arg in prompt["arguments"]:
                    required = " (required)" if arg.get("required") else " (optional)"
                    print(f"    - {arg['name']}{required}")
                    if arg.get("description"):
                        print(f"      {arg['description']}")
    else:
        print("\n  No prompts available from configured MCP servers.")

    # Example: Reading a resource (if any available)
    if resources:
        print("\n" + "=" * 60)
        print("Example: Reading First Resource")
        print("=" * 60)
        first_resource = resources[0]
        try:
            print(f"\nReading: {first_resource['uri']}")
            content = read_mcp_resource(first_resource["server"], first_resource["uri"])

            # Show first 500 characters
            if len(content) > 500:
                print(f"\n{content[:500]}...")
                print(f"\n(Content truncated - total length: {len(content)} characters)")
            else:
                print(f"\n{content}")
        except Exception as e:
            print(f"  Error reading resource: {e}")

    print("\n" + "=" * 60)
    print("Demo Complete")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
