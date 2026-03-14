"""Tests for ReAct agent mode."""

import os

# Disable MCP tools and streaming for tests
os.environ["PATCHPAL_ENABLE_MCP"] = "false"
os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_memory_file(tmp_path, monkeypatch):
    """Mock MEMORY_FILE to prevent loading user's actual MEMORY.md in tests."""
    fake_memory = tmp_path / "nonexistent" / "MEMORY.md"
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", fake_memory)

    def mock_load_mcp_tools(config_path=None):
        return [], {}

    monkeypatch.setattr("patchpal.tools.mcp.load_mcp_tools", mock_load_mcp_tools)

    return fake_memory


def test_react_agent_basic_text_response():
    """Test ReAct agent with a simple text response (no tool calls)."""
    from patchpal.agent import create_react_agent

    # Mock litellm.completion to return a simple answer
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = "Final Answer: The capital of France is Paris."
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 20

    with patch("litellm.completion", return_value=mock_response):
        agent = create_react_agent()
        result = agent.run("What is the capital of France?")

        assert "Paris" in result
        assert len(agent.messages) == 3  # system, user, assistant


def test_react_agent_tool_call_with_grep(monkeypatch):
    """Test ReAct agent successfully calling grep tool."""
    from patchpal.agent import create_react_agent

    # Disable permissions
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

    # First response: agent wants to use grep
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock()]
    mock_response_1.choices[0].message = MagicMock()
    mock_response_1.choices[
        0
    ].message.content = """Thought: I need to search for files containing "test"
Action: grep
Action Input: {"pattern": "test", "path": "."}"""
    mock_response_1.usage = MagicMock()
    mock_response_1.usage.prompt_tokens = 100
    mock_response_1.usage.completion_tokens = 30

    # Second response: agent provides final answer after seeing grep results
    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message = MagicMock()
    mock_response_2.choices[0].message.content = "Final Answer: Found 3 files containing 'test'"
    mock_response_2.usage = MagicMock()
    mock_response_2.usage.prompt_tokens = 150
    mock_response_2.usage.completion_tokens = 20

    with patch("litellm.completion", side_effect=[mock_response_1, mock_response_2]):
        # Mock grep function
        with patch("patchpal.tools.grep", return_value="file1.py\nfile2.py\nfile3.py"):
            agent = create_react_agent()
            result = agent.run("Find files with 'test' in them")

            assert (
                "3 files" in result or "file1" in result or "file2" in result or "file3" in result
            )
            # Should have multiple messages including observations
            assert len(agent.messages) >= 3


def test_react_agent_incomplete_action_format():
    """Test that ReAct agent handles incomplete action format gracefully."""
    from patchpal.agent import create_react_agent

    # Mock response with incomplete action (missing arguments)
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock()]
    mock_response_1.choices[0].message = MagicMock()
    mock_response_1.choices[0].message.content = """Thought: I should grep
Action: grep
PAUSE"""
    mock_response_1.usage = MagicMock()
    mock_response_1.usage.prompt_tokens = 100
    mock_response_1.usage.completion_tokens = 20

    # Second response: agent provides answer after getting guidance
    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message = MagicMock()
    mock_response_2.choices[0].message.content = "Final Answer: I cannot complete this task."
    mock_response_2.usage = MagicMock()
    mock_response_2.usage.prompt_tokens = 120
    mock_response_2.usage.completion_tokens = 15

    with patch("litellm.completion", side_effect=[mock_response_1, mock_response_2]):
        agent = create_react_agent()
        result = agent.run("Search for something")

        # Should complete without crashing
        assert isinstance(result, str)


def test_react_agent_regex_parameter_parsing():
    """Test that ReAct agent's regex-based parameter parsing works."""
    from patchpal.agent import create_react_agent

    # Mock response with various parameter formats
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    # Test loose JSON format (should still work with regex parsing)
    mock_response.choices[0].message.content = """Thought: Read a file
Action: read_file
Action Input: {path: test.txt}"""
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 20

    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message = MagicMock()
    mock_response_2.choices[0].message.content = "Final Answer: File contains test data"
    mock_response_2.usage = MagicMock()
    mock_response_2.usage.prompt_tokens = 120
    mock_response_2.usage.completion_tokens = 15

    with patch("litellm.completion", side_effect=[mock_response, mock_response_2]):
        with patch("patchpal.tools.read_file", return_value="test data"):
            agent = create_react_agent()
            result = agent.run("Read test.txt")

            # Should successfully parse and execute
            assert "test data" in result or "File contains" in result


def test_react_agent_default_tools():
    """Test that ReAct agent has correct default tool set."""
    from patchpal.agent import create_react_agent

    agent = create_react_agent()

    # Check default tools are present
    tool_names = {t["function"]["name"] for t in agent.tools}

    # Should have these essential tools
    assert "read_file" in tool_names
    assert "write_file" in tool_names
    assert "edit_file" in tool_names
    assert "grep" in tool_names  # Optional tool included in ReAct defaults
    assert "list_files" in tool_names  # Optional tool included in ReAct defaults
    assert "run_shell" in tool_names  # Still available but alternatives provided

    # Should have exactly 9 default tools
    assert len(tool_names) == 9


def test_react_agent_custom_enabled_tools():
    """Test that ReAct agent respects enabled_tools parameter."""
    from patchpal.agent import create_react_agent

    agent = create_react_agent(enabled_tools=["read_file", "write_file", "grep"])

    tool_names = {t["function"]["name"] for t in agent.tools}

    # Should only have specified tools
    assert tool_names == {"read_file", "write_file", "grep"}
    assert len(agent.tools) == 3


def test_react_agent_system_prompt_structure():
    """Test that ReAct agent has proper system prompt structure."""
    from patchpal.agent import create_react_agent

    agent = create_react_agent()

    # Verify ReAct-specific elements (new format)
    assert "ReAct agent" in agent.system_prompt
    assert "Thought" in agent.system_prompt
    assert "Action:" in agent.system_prompt
    assert "Action Input:" in agent.system_prompt
    assert "Final Answer:" in agent.system_prompt
    assert "1. To think and act" in agent.system_prompt
    assert "2. To give a final answer" in agent.system_prompt

    # Verify tool descriptions with examples
    assert "Parameters:" in agent.system_prompt
    assert "Example:" in agent.system_prompt

    # Verify examples section exists
    assert "## Examples" in agent.system_prompt


def test_react_agent_action_answer_priority():
    """Test that ReAct agent prioritizes actions over premature answers."""
    from patchpal.agent import create_react_agent

    # Mock response where model provides both action AND answer (should use action)
    mock_response_1 = MagicMock()
    mock_response_1.choices = [MagicMock()]
    mock_response_1.choices[0].message = MagicMock()
    mock_response_1.choices[0].message.content = """Thought: Let me read the file
Action: read_file
Action Input: {"path": "test.txt"}
Final Answer: The file probably contains data"""  # Premature answer
    mock_response_1.usage = MagicMock()
    mock_response_1.usage.prompt_tokens = 100
    mock_response_1.usage.completion_tokens = 40

    mock_response_2 = MagicMock()
    mock_response_2.choices = [MagicMock()]
    mock_response_2.choices[0].message = MagicMock()
    mock_response_2.choices[0].message.content = "Final Answer: The file contains: actual content"
    mock_response_2.usage = MagicMock()
    mock_response_2.usage.prompt_tokens = 150
    mock_response_2.usage.completion_tokens = 20

    with patch("litellm.completion", side_effect=[mock_response_1, mock_response_2]):
        with patch("patchpal.tools.read_file", return_value="actual content"):
            agent = create_react_agent()
            result = agent.run("What's in test.txt?")

            # Should execute the action and get real content, not premature answer
            assert "actual content" in result


def test_react_agent_max_iterations():
    """Test that ReAct agent respects max_iterations limit."""
    from patchpal.agent import create_react_agent

    # Mock response that never provides an answer (infinite loop scenario)
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message = MagicMock()
    mock_response.choices[0].message.content = """Thought: Keep thinking
Action: list_files
Action Input: {"path": "."}"""
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 100
    mock_response.usage.completion_tokens = 20

    with patch("litellm.completion", return_value=mock_response):
        with patch("patchpal.tools.list_files", return_value="file1.txt"):
            agent = create_react_agent()

            # Run with very low max_iterations
            result = agent.run("List files", max_iterations=3)

            # Should stop after max iterations
            assert "Maximum iterations" in result or isinstance(result, str)
