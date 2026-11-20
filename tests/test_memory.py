"""Tests for project memory (MEMORY.md) functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from patchpal.agent import create_agent
from patchpal.tools.common import MEMORY_TEMPLATE


@pytest.fixture
def temp_memory_dir(tmp_path, monkeypatch):
    """Create a temporary directory for MEMORY.md testing."""
    memory_dir = tmp_path / "test_repo"
    memory_dir.mkdir()

    # Mock _get_patchpal_dir to return our temp directory
    monkeypatch.setattr("patchpal.tools.common.PATCHPAL_DIR", memory_dir)

    # Re-initialize MEMORY_FILE with temp directory
    memory_path = memory_dir / "MEMORY.md"
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    return memory_dir


def test_memory_template_content():
    """Test that MEMORY_TEMPLATE has correct content."""
    assert "# Project Memory" in MEMORY_TEMPLATE
    assert "This file persists across PatchPal sessions" in MEMORY_TEMPLATE
    assert "**Project context**" in MEMORY_TEMPLATE
    assert "**Important decisions**" in MEMORY_TEMPLATE
    assert "---" in MEMORY_TEMPLATE


def test_memory_file_creation(temp_memory_dir, monkeypatch):
    """Test that MEMORY.md is created with template if it doesn't exist."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Ensure file doesn't exist
    assert not memory_path.exists()

    # Trigger creation by importing (which calls _ensure_memory_file)
    from patchpal.tools.common import _ensure_memory_file

    # Mock PATCHPAL_DIR for the function
    monkeypatch.setattr("patchpal.tools.common.PATCHPAL_DIR", temp_memory_dir)
    created_path = _ensure_memory_file()

    # Verify file was created
    assert created_path.exists()
    content = created_path.read_text(encoding="utf-8")
    assert "# Project Memory" in content
    assert "---" in content


def test_memory_file_not_overwritten(temp_memory_dir, monkeypatch):
    """Test that existing MEMORY.md is not overwritten."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Create file with custom content
    custom_content = "# My Custom Memory\n\nDon't overwrite me!"
    memory_path.write_text(custom_content, encoding="utf-8")

    # Try to ensure file (should not overwrite)
    from patchpal.tools.common import _ensure_memory_file

    monkeypatch.setattr("patchpal.tools.common.PATCHPAL_DIR", temp_memory_dir)

    result_path = _ensure_memory_file()

    # Verify content was preserved
    assert result_path.read_text(encoding="utf-8") == custom_content


def test_agent_loads_empty_memory(temp_memory_dir, monkeypatch):
    """Test that agent loads empty MEMORY.md with guidance message."""
    memory_path = temp_memory_dir / "MEMORY.md"
    memory_path.write_text(MEMORY_TEMPLATE, encoding="utf-8")

    # Mock MEMORY_FILE
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    # Create agent (no mocking needed - uses real initialization)
    agent = create_agent()

    # Check that memory message was added
    assert len(agent.messages) > 0
    memory_msg = agent.messages[0]

    assert memory_msg["role"] == "system"
    assert "Project Memory (MEMORY.md)" in memory_msg["content"]
    assert "currently empty" in memory_msg["content"]
    assert str(memory_path) in memory_msg["content"]
    assert memory_msg.get("metadata", {}).get("is_memory") is True


def test_agent_loads_populated_memory(temp_memory_dir, monkeypatch):
    """Test that agent loads populated MEMORY.md with full content."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Create populated memory file
    populated_content = """# Project Memory

This file persists across PatchPal sessions.

---

This is a FastAPI project with PostgreSQL backend.
- Use async/await for all database operations
- Authentication via JWT tokens
- Deploy to AWS ECS
"""
    memory_path.write_text(populated_content, encoding="utf-8")

    # Mock MEMORY_FILE
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    # Create agent
    agent = create_agent()

    # Check that memory message was added with full content
    memory_msg = agent.messages[0]

    assert memory_msg["role"] == "system"
    assert "Project Memory (from MEMORY.md)" in memory_msg["content"]
    assert "FastAPI project" in memory_msg["content"]
    assert "PostgreSQL backend" in memory_msg["content"]
    assert "JWT tokens" in memory_msg["content"]
    assert "persists across sessions" in memory_msg["content"]
    assert memory_msg.get("metadata", {}).get("is_memory") is True


def test_memory_content_detection_threshold(temp_memory_dir, monkeypatch):
    """Test that content detection uses 10-char threshold correctly."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Test: exactly 10 chars (should be detected as empty)
    content_10_chars = """# Project Memory

---

0123456789"""
    memory_path.write_text(content_10_chars, encoding="utf-8")
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    agent1 = create_agent()

    # Should show "currently empty" message (threshold is >10, not >=10)
    assert "currently empty" in agent1.messages[0]["content"]

    # Test: 11 chars (should be detected as populated)
    content_11_chars = """# Project Memory

---

01234567890"""
    memory_path.write_text(content_11_chars, encoding="utf-8")

    agent2 = create_agent()

    # Should show full content
    assert "from MEMORY.md" in agent2.messages[0]["content"]
    assert "01234567890" in agent2.messages[0]["content"]


def test_memory_missing_separator(temp_memory_dir, monkeypatch):
    """Test that missing separator is handled correctly."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Create file without "---" separator
    no_separator = """# Project Memory

This has no separator but has content."""
    memory_path.write_text(no_separator, encoding="utf-8")

    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    agent = create_agent()

    # Should be treated as empty (no content after separator)
    assert "currently empty" in agent.messages[0]["content"]


def test_memory_file_read_error(temp_memory_dir, monkeypatch, caplog):
    """Test that file read errors are handled gracefully."""
    memory_path = temp_memory_dir / "MEMORY.md"
    memory_path.write_text(MEMORY_TEMPLATE, encoding="utf-8")

    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    # Mock read_text to raise an exception
    def mock_read_error(*args, **kwargs):
        raise PermissionError("Cannot read file")

    with patch.object(Path, "read_text", side_effect=mock_read_error):
        # Should not raise, agent should initialize
        agent = create_agent()

        # Memory message should not be added if loading failed
        # (graceful failure - silently continue)
        assert agent is not None


def test_memory_whitelisting_in_file_writing(temp_memory_dir, monkeypatch):
    """Test that MEMORY.md is whitelisted for editing without warnings."""
    from patchpal.tools.file_writing import _get_outside_repo_warning

    memory_path = temp_memory_dir / "MEMORY.md"
    memory_path.write_text(MEMORY_TEMPLATE, encoding="utf-8")

    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)
    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", temp_memory_dir / "repo")

    # MEMORY.md should not trigger warning (even though it's outside REPO_ROOT)
    warning = _get_outside_repo_warning(memory_path)
    assert warning == ""

    # Other files outside repo should still trigger warning
    other_file = temp_memory_dir / "other_file.txt"
    warning = _get_outside_repo_warning(other_file)
    assert "WARNING" in warning


def test_memory_unicode_content(temp_memory_dir, monkeypatch):
    """Test that MEMORY.md handles Unicode content correctly."""
    memory_path = temp_memory_dir / "MEMORY.md"

    # Create file with Unicode characters
    unicode_content = """# Project Memory

---

This project uses emojis 🚀 and international characters:
- Japanese: こんにちは
- Arabic: مرحبا
- Emoji: 🎉🎊✨
"""
    memory_path.write_text(unicode_content, encoding="utf-8")

    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    agent = create_agent()

    # Should load successfully with Unicode content
    memory_msg = agent.messages[0]["content"]
    assert "🚀" in memory_msg
    assert "こんにちは" in memory_msg
    assert "مرحبا" in memory_msg


def test_memory_creation_failure_graceful(temp_memory_dir, monkeypatch, caplog):
    """Test that MEMORY.md creation failure is handled gracefully."""
    from patchpal.tools.common import _ensure_memory_file

    # Mock write_text to raise an exception
    def mock_write_error(*args, **kwargs):
        raise PermissionError("Cannot write file")

    with patch.object(Path, "write_text", side_effect=mock_write_error):
        monkeypatch.setattr("patchpal.tools.common.PATCHPAL_DIR", temp_memory_dir)

        # Should not raise exception
        result = _ensure_memory_file()

        # Should return the path even if creation failed
        assert result == temp_memory_dir / "MEMORY.md"


def test_compaction_preserves_memory_message(temp_memory_dir, monkeypatch):
    """Compaction must not summarize away MEMORY.md (it's loaded once and never restored)."""
    from unittest.mock import MagicMock

    memory_path = temp_memory_dir / "MEMORY.md"
    memory_path.write_text(
        "# Project Memory\n\n---\n\nThis is a FastAPI project with PostgreSQL backend.\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("patchpal.tools.common.MEMORY_FILE", memory_path)

    agent = create_agent()
    memory_msg = agent.messages[0]
    assert memory_msg.get("metadata", {}).get("is_memory") is True

    # Mirror the live-test sequence: memory + 2 turns (second with two tool results) + a 3rd turn
    agent.messages += [
        {"role": "user", "content": "list files"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "1", "name": "run_shell", "content": "ls output"},
        {"role": "assistant", "content": "answer 1"},
        {"role": "user", "content": "what does this repo do?"},
        {"role": "assistant", "content": "", "tool_calls": []},
        {"role": "tool", "tool_call_id": "2", "name": "read_file", "content": "README"},
        {"role": "tool", "tool_call_id": "3", "name": "run_shell", "content": "pyproject"},
        {"role": "assistant", "content": "answer 2"},
        {"role": "user", "content": "capital of France?"},
        {"role": "assistant", "content": "Paris."},
    ]

    summary = {"role": "assistant", "content": "[COMPACTION SUMMARY]\n\nsummary"}
    agent.context_manager.create_compaction = MagicMock(return_value=(summary, "summary"))
    agent._perform_auto_compaction()

    # Memory was not sent for summarization
    summarized = agent.context_manager.create_compaction.call_args[0][0]
    assert all(not m.get("metadata", {}).get("is_memory") for m in summarized)

    # Memory is first, followed by the summary and the last 2 turns
    assert agent.messages[0] is memory_msg
    assert agent.messages[1] is summary
    assert agent.messages[2]["content"] == "what does this repo do?"
    assert agent.messages[-1]["content"] == "Paris."
    assert sum(1 for m in agent.messages if m.get("metadata", {}).get("is_memory")) == 1
