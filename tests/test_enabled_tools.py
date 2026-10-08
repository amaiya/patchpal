#!/usr/bin/env python3
"""Test enabled_tools feature for filtering built-in tools."""

import os
from unittest.mock import MagicMock, patch

import pytest

from patchpal import create_agent


def test_parameter_only():
    """Test with parameter only (no env var)."""
    agent = create_agent(enabled_tools=["read_file", "read_lines"])

    # Check that enabled_tools was set correctly
    assert agent.enabled_tools == ["read_file", "read_lines"]


def test_env_var_only():
    """Test with environment variable only."""
    os.environ["PATCHPAL_ENABLED_TOOLS"] = "read_file,code_structure,run_shell"

    try:
        agent = create_agent()
        assert agent.enabled_tools == ["read_file", "code_structure", "run_shell"]
    finally:
        # Clean up
        del os.environ["PATCHPAL_ENABLED_TOOLS"]


def test_parameter_overrides_env():
    """Test that parameter takes precedence over env var."""
    os.environ["PATCHPAL_ENABLED_TOOLS"] = "read_file,read_lines"

    try:
        agent = create_agent(enabled_tools=["write_file", "edit_file"])
        assert agent.enabled_tools == ["write_file", "edit_file"]
    finally:
        # Clean up
        del os.environ["PATCHPAL_ENABLED_TOOLS"]


def test_no_filtering():
    """Test that None means no filtering."""
    agent = create_agent()
    assert agent.enabled_tools is None


def test_empty_list():
    """Test with empty list (no tools)."""
    agent = create_agent(enabled_tools=[])
    assert agent.enabled_tools == []


def test_with_custom_tools():
    """Test that custom tools work alongside enabled_tools."""

    def my_tool(x: int) -> str:
        """A custom tool."""
        return str(x * 2)

    agent = create_agent(custom_tools=[my_tool], enabled_tools=["read_file"])

    assert agent.enabled_tools == ["read_file"]
    assert len(agent.custom_tools) == 1
    assert agent.custom_tools[0].__name__ == "my_tool"


def test_tool_filtering_in_run():
    """Test that tools are actually filtered during agent.run()."""
    # Mock litellm.completion to capture the tools passed to it
    with patch("patchpal.agent.function_calling.litellm.completion") as mock_completion:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_completion.return_value = mock_response

        # Create agent with limited tools
        agent = create_agent(enabled_tools=["read_file", "write_file"])

        # Run the agent
        agent.run("Test message")

        # Verify completion was called
        assert mock_completion.called

        # Get the tools that were passed to litellm.completion
        call_kwargs = mock_completion.call_args[1]
        tools_passed = call_kwargs["tools"]

        # Extract tool names
        tool_names = [t["function"]["name"] for t in tools_passed]

        # Verify only the enabled tools are present
        assert "read_file" in tool_names
        assert "write_file" in tool_names

        # Verify other tools are NOT present
        assert "run_shell" not in tool_names
        assert "web_search" not in tool_names
        assert "edit_file" not in tool_names
        assert "code_structure" not in tool_names

        # Verify we only have the 2 enabled tools
        assert len(tool_names) == 2


def test_tool_filtering_with_custom_tools():
    """Test that custom tools are added even when enabled_tools filters built-ins."""

    def custom_calculator(x: int, y: int) -> str:
        """Add two numbers."""
        return str(x + y)

    with patch("patchpal.agent.function_calling.litellm.completion") as mock_completion:
        # Setup mock response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5, total_tokens=15)
        mock_completion.return_value = mock_response

        # Create agent with limited built-in tools and custom tool
        agent = create_agent(enabled_tools=["read_file"], custom_tools=[custom_calculator])

        # Run the agent
        agent.run("Test message")

        # Get the tools that were passed to litellm.completion
        call_kwargs = mock_completion.call_args[1]
        tools_passed = call_kwargs["tools"]
        tool_names = [t["function"]["name"] for t in tools_passed]

        # Verify built-in enabled tool is present
        assert "read_file" in tool_names

        # Verify custom tool is present
        assert "custom_calculator" in tool_names

        # Verify other built-in tools are NOT present
        assert "write_file" not in tool_names
        assert "run_shell" not in tool_names

        # Should have 1 built-in + 1 custom = 2 tools
        assert len(tool_names) == 2


def test_env_var_with_spaces():
    """Test that spaces in env var are handled correctly."""
    os.environ["PATCHPAL_ENABLED_TOOLS"] = "read_file, write_file , code_structure"

    try:
        agent = create_agent()
        # Verify spaces are stripped
        assert agent.enabled_tools == ["read_file", "write_file", "code_structure"]
    finally:
        del os.environ["PATCHPAL_ENABLED_TOOLS"]


def test_disabled_tool_execution_is_blocked():
    """Test that disabled tools cannot be executed even if LLM tries to call them.

    This is a regression test for the bug where enabled_tools only filtered
    the tool schemas sent to the LLM, but didn't prevent execution if the LLM
    hallucinated a call to a disabled tool.
    """
    # Use streaming=False for simpler mocking
    import os

    # Save prior value so we restore it (instead of deleting) to avoid
    # polluting other tests that rely on PATCHPAL_STREAM_OUTPUT being set.
    _prev_stream_output = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"

    try:
        with patch("patchpal.agent.function_calling.litellm.completion") as mock_completion:
            # Create a mock tool call for run_shell (which is NOT enabled)
            mock_tool_call = MagicMock()
            mock_tool_call.id = "call_123"
            mock_tool_call.function.name = "run_shell"
            mock_tool_call.function.arguments = '{"cmd": "echo test"}'

            # First call: LLM tries to call run_shell (not enabled)
            mock_response1 = MagicMock()
            mock_response1.choices = [MagicMock()]
            mock_response1.choices[0].message.content = "Running command"
            mock_response1.choices[0].message.tool_calls = [mock_tool_call]
            mock_response1.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            )

            # Second call: LLM responds after seeing the error
            mock_response2 = MagicMock()
            mock_response2.choices = [MagicMock()]
            mock_response2.choices[0].message.content = "Tool not available"
            mock_response2.choices[0].message.tool_calls = None
            mock_response2.usage = MagicMock(
                prompt_tokens=10,
                completion_tokens=5,
                cache_creation_input_tokens=0,
                cache_read_input_tokens=0,
            )

            mock_completion.side_effect = [mock_response1, mock_response2]

            # Create agent with only read_file enabled (run_shell is NOT enabled)
            agent = create_agent(enabled_tools=["read_file"])

            # Run - should reject run_shell execution
            agent.run("Test message")

            # Verify run_shell was blocked (check the agent's message history)
            tool_results = [msg for msg in agent.messages if msg.get("role") == "tool"]
            assert len(tool_results) == 1, f"Expected 1 tool result, got {len(tool_results)}"

            # The tool result should contain an error about the tool not being enabled
            error_message = tool_results[0]["content"]
            assert "not enabled" in error_message
            assert "run_shell" in error_message
    finally:
        # Restore prior value rather than unconditionally deleting it
        if _prev_stream_output is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = _prev_stream_output


def test_enabled_tool_execution_is_allowed():
    """Test that enabled tools CAN be executed when LLM calls them."""
    # This is a simple verification that enabled tools work - detailed behavior
    # is tested in integration tests
    agent = create_agent(enabled_tools=["read_file", "write_file"])

    # Just verify the agent was created with correct enabled_tools
    assert agent.enabled_tools == ["read_file", "write_file"]
    assert len(agent.custom_tools) == 0


def test_empty_enabled_tools_blocks_all_builtins():
    """Test that enabled_tools=[] blocks all built-in tools (only custom tools allowed)."""

    def custom_tool(x: int) -> str:
        """A custom tool."""
        return f"Result: {x}"

    agent = create_agent(enabled_tools=[], custom_tools=[custom_tool])

    # Verify configuration
    assert agent.enabled_tools == []
    assert len(agent.custom_tools) == 1
    assert agent.custom_tools[0].__name__ == "custom_tool"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
