"""Tests for system prompt."""

import os

from patchpal.agent import _load_system_prompt


def test_system_prompt_exists():
    """Test that system prompt file exists."""
    import patchpal

    prompt_path = os.path.join(os.path.dirname(patchpal.__file__), "prompts", "system_prompt.md")
    assert os.path.exists(prompt_path), "System prompt file not found"


def test_load_system_prompt():
    """Test that system prompt can be loaded."""
    # Reload the system prompt
    prompt = _load_system_prompt()

    # Verify it loaded
    assert "software engineer assistant" in prompt.lower()
    assert len(prompt) > 100  # Should have substantial content


def test_system_prompt_has_required_sections():
    """Test that system prompt has all required sections."""
    import patchpal

    prompt_path = os.path.join(os.path.dirname(patchpal.__file__), "prompts", "system_prompt.md")

    with open(prompt_path) as f:
        content = f.read()

    # Check for key sections (tools are provided via API, not listed in prompt)
    assert "Key Guidance" in content or "Rules" in content

    # Check that strategic guidance is present
    assert "read_file" in content.lower() or "read files" in content.lower()
    assert "edit_file" in content.lower() or "edit files" in content.lower()

    # Check for key behavioral rules
    assert "concise" in content.lower() or "brevity" in content.lower()
    assert "security" in content.lower()


def test_system_prompt_template_variables():
    """Test that system prompt uses template variables correctly."""
    import patchpal

    prompt_path = os.path.join(os.path.dirname(patchpal.__file__), "prompts", "system_prompt.md")

    with open(prompt_path) as f:
        content = f.read()

    # Check that it uses template variables
    assert "{platform_info}" in content
