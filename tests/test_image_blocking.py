"""Tests for PATCHPAL_BLOCK_IMAGES functionality."""

import pytest


@pytest.fixture(autouse=True)
def mock_memory_file(tmp_path, monkeypatch):
    """Mock MEMORY_FILE to prevent loading user's actual MEMORY.md in tests."""
    fake_memory = tmp_path / "nonexistent" / "MEMORY.md"
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", fake_memory)
    return fake_memory


def test_block_images_disabled_by_default(monkeypatch):
    """Test that BLOCK_IMAGES is disabled by default (images pass through)."""
    # Ensure env var is not set
    monkeypatch.delenv("PATCHPAL_BLOCK_IMAGES", raising=False)

    # Reload config to pick up env change
    import sys

    if "patchpal.agent" in sys.modules:
        del sys.modules["patchpal.agent"]
    if "patchpal.config" in sys.modules:
        del sys.modules["patchpal.config"]

    from patchpal.config import config

    # Verify default is false
    assert config.BLOCK_IMAGES is False


def test_block_images_config_values(monkeypatch):
    """Test that BLOCK_IMAGES config accepts various true/false values."""
    from patchpal.config import config

    # Test true values
    for true_value in ["true", "True", "TRUE", "1", "yes", "Yes"]:
        monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", true_value)
        # Reload config module
        from importlib import reload

        import patchpal.config as config_module

        reload(config_module)
        assert config.BLOCK_IMAGES is True, f"Failed for value: {true_value}"

    # Test false values
    for false_value in ["false", "False", "FALSE", "0", "no", "No"]:
        monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", false_value)
        # Reload config module
        from importlib import reload

        import patchpal.config as config_module

        reload(config_module)
        from patchpal.config import config

        assert config.BLOCK_IMAGES is False, f"Failed for value: {false_value}"


def test_filter_images_disabled(monkeypatch):
    """Test that images pass through when BLOCK_IMAGES=false."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "false")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Simulate messages with images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Look at this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC123"}},
            ],
        },
        {
            "role": "tool",
            "content": [
                {"type": "text", "text": "Image loaded"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,XYZ789"}},
            ],
        },
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # Should pass through unchanged
    assert len(filtered) == 2
    assert len(filtered[0]["content"]) == 2
    assert filtered[0]["content"][1]["type"] == "image_url"
    assert len(filtered[1]["content"]) == 2
    assert filtered[1]["content"][1]["type"] == "image_url"


def test_filter_images_enabled(monkeypatch):
    """Test that images are replaced when BLOCK_IMAGES=true."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "true")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Simulate messages with images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Look at this image"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC123"}},
            ],
        },
        {
            "role": "tool",
            "content": [
                {"type": "text", "text": "Image loaded"},
                {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,XYZ789"}},
            ],
        },
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # Should replace images with text
    assert len(filtered) == 2
    assert len(filtered[0]["content"]) == 2
    assert filtered[0]["content"][1]["type"] == "text"
    assert "[Image blocked" in filtered[0]["content"][1]["text"]
    assert len(filtered[1]["content"]) == 2
    assert filtered[1]["content"][1]["type"] == "text"
    assert "[Image blocked" in filtered[1]["content"][1]["text"]


def test_filter_images_deduplication(monkeypatch):
    """Test that consecutive image placeholders are deduplicated."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "true")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Multiple consecutive images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC"}},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,DEF"}},
                {"type": "text", "text": "Between"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,GHI"}},
            ],
        }
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # Should dedupe consecutive placeholders
    assert len(filtered[0]["content"]) == 3  # 1 placeholder + text + 1 placeholder
    assert filtered[0]["content"][0]["type"] == "text"
    assert "[Image blocked" in filtered[0]["content"][0]["text"]
    assert filtered[0]["content"][1]["type"] == "text"
    assert filtered[0]["content"][1]["text"] == "Between"
    assert filtered[0]["content"][2]["type"] == "text"
    assert "[Image blocked" in filtered[0]["content"][2]["text"]


def test_filter_images_preserves_text(monkeypatch):
    """Test that text content is preserved when filtering images."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "true")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Mixed text and images
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "First text"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC"}},
                {"type": "text", "text": "Second text"},
            ],
        }
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # Text should be preserved
    assert filtered[0]["content"][0]["type"] == "text"
    assert filtered[0]["content"][0]["text"] == "First text"
    assert filtered[0]["content"][1]["type"] == "text"
    assert "[Image blocked" in filtered[0]["content"][1]["text"]
    assert filtered[0]["content"][2]["type"] == "text"
    assert filtered[0]["content"][2]["text"] == "Second text"


def test_filter_images_only_affects_user_and_tool_messages(monkeypatch):
    """Test that filtering only applies to user and tool messages."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "true")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Messages with different roles
    messages = [
        {"role": "system", "content": "System message"},
        {"role": "assistant", "content": "Assistant message"},
        {
            "role": "user",
            "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,ABC"}}],
        },
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # System and assistant messages should be unchanged
    assert filtered[0] == messages[0]
    assert filtered[1] == messages[1]

    # User message should have image filtered
    assert filtered[2]["content"][0]["type"] == "text"
    assert "[Image blocked" in filtered[2]["content"][0]["text"]


def test_filter_images_handles_string_content(monkeypatch):
    """Test that filtering handles messages with string content (not list)."""
    monkeypatch.setenv("PATCHPAL_BLOCK_IMAGES", "true")
    monkeypatch.setenv("PATCHPAL_ENABLE_MCP", "false")

    # Reload modules
    import sys

    for module in ["patchpal.config", "patchpal.agent"]:
        if module in sys.modules:
            del sys.modules[module]

    from patchpal.agent import PatchPalAgent

    agent = PatchPalAgent(model_id="anthropic/claude-sonnet-4-5")

    # Messages with string content (not multimodal)
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there"},
    ]

    filtered = agent.image_handler.filter_images_if_blocked(messages)

    # Should pass through unchanged
    assert filtered == messages
