#!/usr/bin/env python3
"""Test optional tools (grep and find) that are disabled by default."""

from patchpal import create_agent
from patchpal.tools.definitions import TOOL_FUNCTIONS, get_tools


def test_optional_tools_disabled_by_default():
    """Optional tools should not be in default tools list."""
    tools, functions = get_tools()

    tool_names = [t["function"]["name"] for t in tools]

    # Optional tools should NOT be in default tools
    assert "grep" not in tool_names
    assert "find" not in tool_names
    print("✓ grep and find not in default tools")

    # But they SHOULD be in TOOL_FUNCTIONS (so they can be enabled)
    assert "grep" in TOOL_FUNCTIONS
    assert "find" in TOOL_FUNCTIONS
    assert "grep" in functions
    assert "find" in functions
    print("✓ grep and find are in TOOL_FUNCTIONS (available for enabled_tools)")


def test_optional_tools_can_be_enabled():
    """Optional tools should be usable when explicitly enabled."""
    agent = create_agent(enabled_tools=["read_file", "grep", "find"])

    assert agent.enabled_tools == ["read_file", "grep", "find"]
    print(f"✓ Agent created with optional tools enabled: {agent.enabled_tools}")


def test_default_agent_no_optional_tools():
    """Default agent should not have optional tools."""
    agent = create_agent()

    assert agent.enabled_tools is None
    print("✓ Default agent has no filtering (enabled_tools=None)")


def test_lightweight_readonly_agent():
    """Test the lightweight read-only + navigation use case."""
    agent = create_agent(enabled_tools=["read_file", "read_lines", "find", "grep"])

    assert "find" in agent.enabled_tools
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
    assert "find" not in agent.enabled_tools
    print("✓ grep can be enabled independently")


def test_find_only():
    """Test enabling just find."""
    agent = create_agent(enabled_tools=["read_file", "find"])

    assert "find" in agent.enabled_tools
    assert "grep" not in agent.enabled_tools
    print("✓ find can be enabled independently")


def test_optional_tools_actually_passed_to_llm():
    """Test that optional tools are actually passed to litellm.completion() when enabled."""
    from unittest.mock import MagicMock, patch

    # Import litellm directly and patch it there
    import litellm

    with patch.object(litellm, "completion") as mock_completion:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_completion.return_value = mock_response

        # Create agent with optional tools enabled
        agent = create_agent(enabled_tools=["read_file", "grep", "find"])

        # Run the agent
        agent.run("Test message")

        # Verify completion was called
        assert mock_completion.called

        # Get the tools that were passed to litellm.completion
        call_kwargs = mock_completion.call_args[1]
        tools_passed = call_kwargs["tools"]

        # Extract tool names
        tool_names = [t["function"]["name"] for t in tools_passed]

        # Verify optional tools are actually in the tools passed to LLM
        assert "grep" in tool_names, "grep should be passed to LLM when enabled"
        assert "find" in tool_names, "find should be passed to LLM when enabled"
        assert "read_file" in tool_names

        # Verify other tools are NOT present
        assert "run_shell" not in tool_names
        assert "web_search" not in tool_names

        # Verify we only have the 3 enabled tools
        assert len(tool_names) == 3
        print("✓ Optional tools are actually passed to LLM when enabled")


if __name__ == "__main__":
    print("Testing optional tools (grep, find)\n" + "=" * 60)

    test_optional_tools_disabled_by_default()
    test_optional_tools_can_be_enabled()
    test_default_agent_no_optional_tools()
    test_lightweight_readonly_agent()
    test_grep_only()
    test_find_only()

    print("\n" + "=" * 60)
    print("✓ All tests passed! Optional tools work correctly.")
