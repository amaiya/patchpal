"""Test reasoning_content capture for gpt-oss and similar models."""

from unittest.mock import Mock, patch

from patchpal.agent.function_calling import PatchPalAgent


def test_reasoning_content_captured():
    """Test that reasoning_content is captured from LLM responses."""
    # Create a mock response with reasoning_content
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me help you with that."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.reasoning_content = "First, I need to understand the task..."
    mock_response.choices[0].message.thinking_blocks = None

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests and enable reasoning capture
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent and mock at the module level
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="openai/gpt-oss-20b")

            # Run agent with a simple message
            agent.run("Hello")

            # Check that reasoning_content was stored in messages
            # messages[0] is the memory system message, messages[1] is user, messages[2] is assistant
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" in assistant_msg
            assert assistant_msg["reasoning_content"] == "First, I need to understand the task..."
    finally:
        # Restore original values
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_reasoning_field_captured():
    """Test that 'reasoning' field is also captured and mapped to reasoning_content."""
    # Some providers use 'reasoning' instead of 'reasoning_content'
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me help you with that."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.reasoning = "I should consider the following approach..."
    # No reasoning_content attribute
    mock_response.choices[0].message.reasoning_content = None
    mock_response.choices[0].message.thinking_blocks = None

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="ollama_chat/gpt-oss:120b")

            # Run agent
            agent.run("Hello")

            # Check that reasoning was mapped to reasoning_content
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" in assistant_msg
            assert (
                assistant_msg["reasoning_content"] == "I should consider the following approach..."
            )
    finally:
        # Restore original value
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_thinking_blocks_captured():
    """Test that thinking_blocks are captured for Anthropic extended thinking."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me think about this carefully."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.reasoning_content = None
    mock_response.choices[0].message.thinking_blocks = [
        {
            "type": "thinking",
            "thinking": "This requires careful analysis...",
            "signature": "abc123...",
        }
    ]

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="anthropic/claude-3-7-sonnet-20250219")

            # Run agent
            agent.run("Hello")

            # Check that thinking_blocks were stored
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "thinking_blocks" in assistant_msg
            assert len(assistant_msg["thinking_blocks"]) == 1
            assert (
                assistant_msg["thinking_blocks"][0]["thinking"]
                == "This requires careful analysis..."
            )
    finally:
        # Restore original value
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_reasoning_content_passed_back():
    """Test that reasoning_content is passed back in subsequent requests."""
    # Disable streaming for tests
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # First response with reasoning_content
        mock_response_1 = Mock()
        mock_response_1.choices = [Mock()]
        mock_response_1.choices[0].message = Mock()
        mock_response_1.choices[0].message.content = "Let me check that file."
        mock_response_1.choices[0].message.tool_calls = [Mock()]
        mock_response_1.choices[0].message.tool_calls[0].id = "call_123"
        mock_response_1.choices[0].message.tool_calls[0].function.name = "read_file"
        mock_response_1.choices[0].message.tool_calls[0].function.arguments = '{"path": "test.py"}'
        mock_response_1.choices[0].message.reasoning_content = "I need to read test.py first..."
        mock_response_1.choices[0].message.thinking_blocks = None
        mock_usage_1 = Mock()
        mock_usage_1.prompt_tokens = 100
        mock_usage_1.completion_tokens = 50
        mock_usage_1.cache_creation_input_tokens = None
        mock_usage_1.cache_read_input_tokens = None
        mock_usage_1.prompt_tokens_details = None
        mock_response_1.usage = mock_usage_1

        # Second response (after tool result)
        mock_response_2 = Mock()
        mock_response_2.choices = [Mock()]
        mock_response_2.choices[0].message = Mock()
        mock_response_2.choices[0].message.content = "The file contains..."
        mock_response_2.choices[0].message.tool_calls = None
        mock_response_2.choices[0].message.reasoning_content = "Now I can see the contents..."
        mock_response_2.choices[0].message.thinking_blocks = None
        mock_usage_2 = Mock()
        mock_usage_2.prompt_tokens = 150
        mock_usage_2.completion_tokens = 60
        mock_usage_2.cache_creation_input_tokens = None
        mock_usage_2.cache_read_input_tokens = None
        mock_usage_2.prompt_tokens_details = None
        mock_response_2.usage = mock_usage_2

        call_count = [0]
        captured_messages = []

        def mock_completion(**kwargs):
            captured_messages.append(kwargs.get("messages", []))
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_response_1
            else:
                return mock_response_2

        # Mock read_file to return dummy content
        with patch("litellm.completion", side_effect=mock_completion):
            with patch("patchpal.tools.file_reading.read_file", return_value="def test(): pass"):
                agent = PatchPalAgent(model_id="openai/gpt-oss-20b")

                # Run agent - should make tool call
                agent.run("Read test.py")

                # Verify we made 2 LLM calls
                assert call_count[0] == 2

                # Check that second call included reasoning_content from first response
                second_call_messages = captured_messages[1]

                # Find the assistant message with tool_calls
                assistant_with_tools = None
                for msg in second_call_messages:
                    if msg.get("role") == "assistant" and msg.get("tool_calls"):
                        assistant_with_tools = msg
                        break

                # Verify reasoning_content was passed back
                assert assistant_with_tools is not None
                assert "reasoning_content" in assistant_with_tools
                assert (
                    assistant_with_tools["reasoning_content"] == "I need to read test.py first..."
                )
    finally:
        # Restore original value
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_no_reasoning_content_no_error():
    """Test that missing reasoning_content doesn't cause errors."""
    # Response without reasoning_content (normal case for non-reasoning models)
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Hello there!"
    mock_response.choices[0].message.tool_calls = None
    # No reasoning fields at all
    mock_response.choices[0].message.reasoning_content = None
    mock_response.choices[0].message.reasoning = None
    mock_response.choices[0].message.thinking_blocks = None
    mock_usage = Mock()
    mock_usage.prompt_tokens = 50
    mock_usage.completion_tokens = 20
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

            # Should work fine without reasoning fields
            agent.run("Hello")

            # Check that message was stored without reasoning_content
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" not in assistant_msg
            assert "thinking_blocks" not in assistant_msg
    finally:
        # Restore original value
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_reasoning_capture_enabled_by_default():
    """Test that reasoning_content IS captured by default (no explicit flag set)."""
    # Create a mock response with reasoning_content
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me help you with that."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.reasoning_content = "Default behavior should capture this..."
    mock_response.choices[0].message.thinking_blocks = None

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests, and DON'T set PATCHPAL_CAPTURE_REASONING (test default)
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    # Remove the flag to test default behavior
    if "PATCHPAL_CAPTURE_REASONING" in os.environ:
        del os.environ["PATCHPAL_CAPTURE_REASONING"]

    try:
        # Create agent and mock at the module level
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="openai/gpt-oss-20b")

            # Run agent with a simple message
            agent.run("Hello")

            # Check that reasoning_content WAS captured (default behavior)
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" in assistant_msg  # SHOULD be captured by default
            assert assistant_msg["reasoning_content"] == "Default behavior should capture this..."
    finally:
        # Restore original values
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            if "PATCHPAL_CAPTURE_REASONING" in os.environ:
                del os.environ["PATCHPAL_CAPTURE_REASONING"]
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_reasoning_text_field_captured():
    """Test that 'reasoning_text' field is also captured and mapped to reasoning_content."""
    # Some providers use 'reasoning_text' instead of 'reasoning_content' or 'reasoning'
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me help you with that."
    mock_response.choices[0].message.tool_calls = None
    mock_response.choices[0].message.reasoning_text = "Third field variant to check..."
    # No reasoning_content or reasoning attributes
    mock_response.choices[0].message.reasoning_content = None
    mock_response.choices[0].message.reasoning = None
    mock_response.choices[0].message.thinking_blocks = None

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests and enable reasoning capture
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="ollama_chat/some-model:latest")

            # Run agent
            agent.run("Hello")

            # Check that reasoning_text was mapped to reasoning_content
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" in assistant_msg
            assert assistant_msg["reasoning_content"] == "Third field variant to check..."
    finally:
        # Restore original values
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture


def test_reasoning_field_priority():
    """Test that reasoning_content takes priority over reasoning over reasoning_text."""
    # If multiple fields are present, use the first non-empty one in priority order
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "Let me help you with that."
    mock_response.choices[0].message.tool_calls = None
    # Set all three fields - reasoning_content should win
    mock_response.choices[0].message.reasoning_content = "This should be captured (priority 1)"
    mock_response.choices[0].message.reasoning = "Not this one (priority 2)"
    mock_response.choices[0].message.reasoning_text = "Not this either (priority 3)"
    mock_response.choices[0].message.thinking_blocks = None

    # Mock usage for cost tracking (use real integers, not Mock objects)
    mock_usage = Mock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = 50
    mock_usage.cache_creation_input_tokens = None
    mock_usage.cache_read_input_tokens = None
    mock_usage.prompt_tokens_details = None
    mock_response.usage = mock_usage

    # Disable streaming for tests and enable reasoning capture
    import os

    old_stream = os.environ.get("PATCHPAL_STREAM_OUTPUT")
    old_capture = os.environ.get("PATCHPAL_CAPTURE_REASONING")
    os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
    os.environ["PATCHPAL_CAPTURE_REASONING"] = "true"

    try:
        # Create agent
        with patch("litellm.completion", return_value=mock_response):
            agent = PatchPalAgent(model_id="openai/gpt-oss-20b")

            # Run agent
            agent.run("Hello")

            # Check that reasoning_content (first priority) was captured
            assistant_msg = None
            for msg in agent.messages:
                if msg.get("role") == "assistant":
                    assistant_msg = msg
                    break

            assert assistant_msg is not None
            assert "reasoning_content" in assistant_msg
            assert assistant_msg["reasoning_content"] == "This should be captured (priority 1)"
    finally:
        # Restore original values
        if old_stream is None:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)
        else:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_stream
        if old_capture is None:
            os.environ.pop("PATCHPAL_CAPTURE_REASONING", None)
        else:
            os.environ["PATCHPAL_CAPTURE_REASONING"] = old_capture
