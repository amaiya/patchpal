#!/usr/bin/env python3
"""Test optional tools (grep and list_files) that are disabled by default."""

from patchpal import create_agent
from patchpal.tools.definitions import TOOL_FUNCTIONS, get_tools


def test_optional_tools_disabled_by_default():
    """Optional tools should not be in default tools list."""
    tools, functions = get_tools()

    tool_names = [t["function"]["name"] for t in tools]

    # Optional tools should NOT be in default tools
    assert "grep" not in tool_names
    assert "list_files" not in tool_names
    print("✓ grep and list_files not in default tools")

    # But they SHOULD be in TOOL_FUNCTIONS (so they can be enabled)
    assert "grep" in TOOL_FUNCTIONS
    assert "list_files" in TOOL_FUNCTIONS
    assert "grep" in functions
    assert "list_files" in functions
    print("✓ grep and list_files are in TOOL_FUNCTIONS (available for enabled_tools)")


def test_optional_tools_can_be_enabled():
    """Optional tools should be usable when explicitly enabled."""
    agent = create_agent(enabled_tools=["read_file", "grep", "list_files"])

    assert agent.enabled_tools == ["read_file", "grep", "list_files"]
    print(f"✓ Agent created with optional tools enabled: {agent.enabled_tools}")


def test_default_agent_no_optional_tools():
    """Default agent should not have optional tools."""
    agent = create_agent()

    assert agent.enabled_tools is None
    print("✓ Default agent has no filtering (enabled_tools=None)")


def test_lightweight_readonly_agent():
    """Test the lightweight read-only + navigation use case."""
    agent = create_agent(enabled_tools=["read_file", "read_lines", "list_files", "grep"])

    assert "list_files" in agent.enabled_tools
    assert "grep" in agent.enabled_tools
    assert "read_file" in agent.enabled_tools

    # Verify no expensive or dangerous tools
    assert "get_repo_map" not in agent.enabled_tools
    assert "run_shell" not in agent.enabled_tools
    assert "edit_file" not in agent.enabled_tools
    print(f"✓ Lightweight read-only agent: {agent.enabled_tools}")


def test_grep_only():
    """Test enabling just grep."""
    agent = create_agent(enabled_tools=["read_file", "grep"])

    assert "grep" in agent.enabled_tools
    assert "list_files" not in agent.enabled_tools
    print("✓ grep can be enabled independently")


def test_list_files_only():
    """Test enabling just list_files."""
    agent = create_agent(enabled_tools=["read_file", "list_files"])

    assert "list_files" in agent.enabled_tools
    assert "grep" not in agent.enabled_tools
    print("✓ list_files can be enabled independently")


if __name__ == "__main__":
    print("Testing optional tools (grep, list_files)\n" + "=" * 60)

    test_optional_tools_disabled_by_default()
    test_optional_tools_can_be_enabled()
    test_default_agent_no_optional_tools()
    test_lightweight_readonly_agent()
    test_grep_only()
    test_list_files_only()

    print("\n" + "=" * 60)
    print("✓ All tests passed! Optional tools work correctly.")
