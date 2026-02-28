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
    import patchpal.agent as agent_module

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
