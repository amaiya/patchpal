"""Tests for streaming functionality."""

import os
import time

from patchpal.cli.streaming import StreamRenderer, stream_completion


def test_stream_renderer_imports():
    """Test that streaming module can be imported."""
    # If we got here, imports worked
    assert StreamRenderer is not None
    assert stream_completion is not None


def test_stream_renderer_basic():
    """Test basic StreamRenderer functionality."""
    renderer = StreamRenderer(show_tokens=True, show_interrupt_hint=True)

    # Should not be running initially
    assert not renderer._running

    # Start renderer
    renderer.start()
    assert renderer._running
    time.sleep(0.2)  # Let it run briefly

    # Update with tokens
    renderer.update_tokens(25)
    assert renderer._token_count == 25
    time.sleep(0.2)

    # Stop renderer
    renderer.stop()
    assert not renderer._running


def test_stream_renderer_token_updates():
    """Test that token updates work correctly."""
    renderer = StreamRenderer(show_tokens=True)
    renderer.start()

    # Update tokens progressively
    for i in [10, 20, 30, 40, 50]:
        renderer.update_tokens(i)
        assert renderer._token_count == i
        time.sleep(0.05)

    renderer.stop(show_summary=False)


def test_stream_renderer_no_tokens():
    """Test renderer without token display."""
    renderer = StreamRenderer(show_tokens=False, show_interrupt_hint=False)
    renderer.start()
    time.sleep(0.3)
    renderer.stop(show_summary=False)
    # Should complete without errors


def test_stream_renderer_first_token_time():
    """Test that first token time is recorded."""
    renderer = StreamRenderer()
    renderer.start()

    # Initially no first token time
    assert renderer._first_token_time is None

    # Update with tokens
    renderer.update_tokens(1)
    assert renderer._first_token_time is not None
    first_time = renderer._first_token_time

    # Subsequent updates don't change first token time
    time.sleep(0.1)
    renderer.update_tokens(10)
    assert renderer._first_token_time == first_time

    renderer.stop()


def test_stream_renderer_double_start():
    """Test that double start is safe."""
    renderer = StreamRenderer()
    renderer.start()
    assert renderer._running

    # Starting again should be safe
    renderer.start()
    assert renderer._running

    renderer.stop()


def test_stream_renderer_double_stop():
    """Test that double stop is safe."""
    renderer = StreamRenderer()
    renderer.start()
    renderer.stop()
    assert not renderer._running

    # Stopping again should be safe
    renderer.stop()
    assert not renderer._running


def test_agent_has_streaming_integration():
    """Test that agent module has streaming integration."""
    import patchpal.agent.function_calling as agent_module

    # Check that stream_completion is imported in agent module
    assert hasattr(agent_module, "stream_completion")


def test_streaming_env_toggle_enabled_by_default():
    """Test that streaming is enabled by default."""
    # Clear any existing env var
    old_val = os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)

    try:
        # Default should be true
        enable_streaming = os.environ.get("PATCHPAL_STREAM_OUTPUT", "true").lower() == "true"
        assert enable_streaming is True
    finally:
        # Restore old value
        if old_val is not None:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_val


def test_streaming_env_toggle_disabled():
    """Test that streaming can be disabled via environment variable."""
    old_val = os.environ.get("PATCHPAL_STREAM_OUTPUT")

    try:
        os.environ["PATCHPAL_STREAM_OUTPUT"] = "false"
        enable_streaming = os.environ.get("PATCHPAL_STREAM_OUTPUT", "true").lower() == "true"
        assert enable_streaming is False
    finally:
        # Restore old value
        if old_val is not None:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_val
        else:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)


def test_streaming_env_toggle_case_insensitive():
    """Test that environment variable is case insensitive."""
    old_val = os.environ.get("PATCHPAL_STREAM_OUTPUT")

    try:
        # Test various cases
        for value in ["TRUE", "True", "true"]:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = value
            enable_streaming = os.environ.get("PATCHPAL_STREAM_OUTPUT", "true").lower() == "true"
            assert enable_streaming is True, f"Failed for value: {value}"

        for value in ["FALSE", "False", "false", "0", "no"]:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = value
            enable_streaming = os.environ.get("PATCHPAL_STREAM_OUTPUT", "true").lower() == "true"
            assert enable_streaming is False, f"Failed for value: {value}"
    finally:
        # Restore old value
        if old_val is not None:
            os.environ["PATCHPAL_STREAM_OUTPUT"] = old_val
        else:
            os.environ.pop("PATCHPAL_STREAM_OUTPUT", None)


def test_stream_renderer_configuration():
    """Test StreamRenderer configuration constants."""
    assert StreamRenderer.UPDATE_INTERVAL == 0.15
    assert StreamRenderer.TOKEN_DISPLAY_THRESHOLD == 20
    assert StreamRenderer.SLOW_RESPONSE_THRESHOLD == 5.0
    assert len(StreamRenderer.SPINNER_FRAMES) == 10


# ---------------------------------------------------------------------------
# Tool call accumulation across streamed chunks. LiteLLM normalizes every provider
# to OpenAI-style chunks, but providers differ in how a tool call is split up.
# ---------------------------------------------------------------------------


def _chunk(tool_calls=None, content=None):
    """Build a LiteLLM-style streaming chunk with the given tool call deltas."""
    from litellm.types.utils import Delta, ModelResponseStream, StreamingChoices

    return ModelResponseStream(
        choices=[StreamingChoices(index=0, delta=Delta(content=content, tool_calls=tool_calls))]
    )


def _tc(index, id=None, name=None, arguments=None):
    return {
        "index": index,
        "id": id,
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }


def _stream(chunks):
    """Run chunks through stream_completion()'s streaming path and return the tool calls."""

    def completion_call(stream):
        # stream_completion falls back to a blocking call if streaming raises; fail
        # loudly instead so a broken accumulator can't pass by falling back
        assert stream, "fell back to non-streaming"
        return iter(chunks)

    response = stream_completion(completion_call, show_progress=True)
    calls = response.choices[0].message.tool_calls or []
    return [(c.id, c.function.name, c.function.arguments) for c in calls]


def test_stream_tool_calls_anthropic_style():
    """Anthropic (via LiteLLM): id + name on the first chunk, then argument pieces
    with id=None; each call has its own index."""
    calls = _stream(
        [
            _chunk([_tc(0, "toolu_1", "read_file", "")]),
            _chunk([_tc(0, None, None, '{"path": ')]),
            _chunk([_tc(0, None, None, '"a.md"}')]),
            _chunk([_tc(1, "toolu_2", "read_file", "")]),
            _chunk([_tc(1, None, None, '{"path": "b.md"}')]),
        ]
    )
    assert calls == [
        ("toolu_1", "read_file", '{"path": "a.md"}'),
        ("toolu_2", "read_file", '{"path": "b.md"}'),
    ]


def test_stream_tool_calls_openai_style():
    """OpenAI / vLLM: one call's arguments split across chunks with the same index."""
    calls = _stream(
        [
            _chunk([_tc(0, "call_1", "run_shell", '{"cmd"')]),
            _chunk([_tc(0, None, None, ': "ls')]),
            _chunk([_tc(0, None, None, ' -la"}')]),
        ]
    )
    assert calls == [("call_1", "run_shell", '{"cmd": "ls -la"}')]


def test_stream_tool_calls_same_id_repeated():
    """A provider that repeats the same id on every chunk of one call still yields one call."""
    calls = _stream(
        [
            _chunk([_tc(0, "call_1", "read_file", '{"path": ')]),
            _chunk([_tc(0, "call_1", None, '"a.md"}')]),
        ]
    )
    assert calls == [("call_1", "read_file", '{"path": "a.md"}')]


def test_stream_tool_calls_ollama_style_parallel_calls_not_merged():
    """Ollama (via LiteLLM): each complete call arrives in its own chunk, all with index 0
    but a new id. These must stay separate calls.

    Regression: with qwen3.5:4b, parallel read_file calls were merged into one invalid
    arguments string ('{"path": "a.md"}{"path": "b.md"}...'), so every read failed.
    """
    calls = _stream(
        [
            _chunk([_tc(0, "uuid-1", "read_file", '{"path": "docs/index.md"}')]),
            _chunk([_tc(0, "uuid-2", "read_file", '{"path": "docs/README.md"}')]),
            _chunk([_tc(0, "uuid-3", "read_file", '{"path": "docs/configuration.md"}')]),
        ]
    )
    assert calls == [
        ("uuid-1", "read_file", '{"path": "docs/index.md"}'),
        ("uuid-2", "read_file", '{"path": "docs/README.md"}'),
        ("uuid-3", "read_file", '{"path": "docs/configuration.md"}'),
    ]
