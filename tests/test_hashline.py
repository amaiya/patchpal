"""Tests for hashline editing functionality."""

import pytest

from patchpal.tools.hashline import (
    AppendEdit,
    HashlineMismatchError,
    InsertEdit,
    PrependEdit,
    ReplaceEdit,
    SetEdit,
    apply_hashline_edits,
    compute_line_hash,
    format_hash_lines,
    parse_tag,
)


def test_compute_line_hash():
    """Test hash computation."""
    # Same content should produce same hash
    hash1 = compute_line_hash(1, "def foo():")
    hash2 = compute_line_hash(1, "def foo():")
    assert hash1 == hash2

    # Different content should (usually) produce different hash
    hash3 = compute_line_hash(1, "def bar():")
    assert hash1 != hash3

    # Whitespace normalized - these should be the same
    hash4 = compute_line_hash(1, "def   foo():")
    assert hash1 == hash4


def test_format_hash_lines():
    """Test formatting content with hashlines."""
    content = "line1\nline2\nline3"
    formatted = format_hash_lines(content)

    lines = formatted.split("\n")
    assert len(lines) == 3
    assert lines[0].startswith("1#")
    assert lines[1].startswith("2#")
    assert lines[2].startswith("3#")

    # Check format: LINE#HASH:CONTENT
    assert ":line1" in lines[0]
    assert ":line2" in lines[1]
    assert ":line3" in lines[2]


def test_parse_tag():
    """Test parsing line references."""
    tag = parse_tag("5#ZP")
    assert tag.line == 5
    assert tag.hash == "ZP"

    # Should handle extra whitespace
    tag2 = parse_tag("  10#MQ  ")
    assert tag2.line == 10
    assert tag2.hash == "MQ"

    # Should handle display suffix
    tag3 = parse_tag("3#VR:some content")
    assert tag3.line == 3
    assert tag3.hash == "VR"

    # Invalid formats should raise
    with pytest.raises(ValueError):
        parse_tag("not-a-tag")

    with pytest.raises(ValueError):
        parse_tag("5#")  # Missing hash


def test_set_edit():
    """Test SetEdit operation."""
    content = "line1\nline2\nline3"
    hash2 = compute_line_hash(2, "line2")

    edit = SetEdit(tag=parse_tag(f"2#{hash2}"), content=["replaced"])
    result = apply_hashline_edits(content, [edit])

    assert result.content == "line1\nreplaced\nline3"
    assert result.first_changed_line == 2


def test_replace_edit():
    """Test ReplaceEdit operation."""
    content = "line1\nline2\nline3\nline4"
    hash2 = compute_line_hash(2, "line2")
    hash3 = compute_line_hash(3, "line3")

    edit = ReplaceEdit(
        first=parse_tag(f"2#{hash2}"), last=parse_tag(f"3#{hash3}"), content=["new line"]
    )
    result = apply_hashline_edits(content, [edit])

    assert result.content == "line1\nnew line\nline4"
    assert result.first_changed_line == 2


def test_append_edit():
    """Test AppendEdit operation."""
    content = "line1\nline2\nline3"
    hash2 = compute_line_hash(2, "line2")

    # Append after specific line
    edit = AppendEdit(content=["appended"], after=parse_tag(f"2#{hash2}"))
    result = apply_hashline_edits(content, [edit])

    assert result.content == "line1\nline2\nappended\nline3"
    assert result.first_changed_line == 3

    # Append at EOF
    edit_eof = AppendEdit(content=["at end"])
    result2 = apply_hashline_edits(content, [edit_eof])
    assert result2.content == "line1\nline2\nline3\nat end"


def test_prepend_edit():
    """Test PrependEdit operation."""
    content = "line1\nline2\nline3"
    hash2 = compute_line_hash(2, "line2")

    # Prepend before specific line
    edit = PrependEdit(content=["prepended"], before=parse_tag(f"2#{hash2}"))
    result = apply_hashline_edits(content, [edit])

    assert result.content == "line1\nprepended\nline2\nline3"
    assert result.first_changed_line == 2

    # Prepend at BOF
    edit_bof = PrependEdit(content=["at start"])
    result2 = apply_hashline_edits(content, [edit_bof])
    assert result2.content == "at start\nline1\nline2\nline3"


def test_insert_edit():
    """Test InsertEdit operation."""
    content = "line1\nline2\nline3"
    hash1 = compute_line_hash(1, "line1")
    hash2 = compute_line_hash(2, "line2")

    edit = InsertEdit(
        after=parse_tag(f"1#{hash1}"), before=parse_tag(f"2#{hash2}"), content=["inserted"]
    )
    result = apply_hashline_edits(content, [edit])

    assert result.content == "line1\ninserted\nline2\nline3"
    assert result.first_changed_line == 2


def test_hash_mismatch_error():
    """Test hash mismatch detection."""
    content = "line1\nline2\nline3"

    # Use wrong hash
    edit = SetEdit(tag=parse_tag("2#XX"), content=["should fail"])

    with pytest.raises(HashlineMismatchError) as exc_info:
        apply_hashline_edits(content, [edit])

    error = exc_info.value
    assert len(error.mismatches) == 1
    assert error.mismatches[0].line == 2
    assert error.mismatches[0].expected == "XX"

    # Error should show correct hash in remaps
    assert "2#XX" in error.remaps
    correct_ref = error.remaps["2#XX"]
    assert correct_ref.startswith("2#")


def test_multiple_edits():
    """Test applying multiple edits in one call."""
    content = "line1\nline2\nline3\nline4"

    hash1 = compute_line_hash(1, "line1")
    hash4 = compute_line_hash(4, "line4")

    edits = [
        SetEdit(tag=parse_tag(f"1#{hash1}"), content=["first changed"]),
        SetEdit(tag=parse_tag(f"4#{hash4}"), content=["last changed"]),
    ]

    result = apply_hashline_edits(content, edits)

    assert result.content == "first changed\nline2\nline3\nlast changed"
    assert result.first_changed_line == 1


def test_edit_file_hashline(tmp_path, monkeypatch):
    """Test the edit_file_hashline function."""
    # Setup test environment
    test_file = tmp_path / "test.py"
    test_file.write_text("def foo():\n    return 42\n\ndef bar():\n    pass\n")

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    import patchpal.tools.common

    patchpal.tools.common._permission_manager = None

    # Monkey-patch REPO_ROOT to include tmp_path
    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", tmp_path)

    from patchpal.tools.file_editing import edit_file_hashline

    # Read to get hashes
    _ = test_file.read_text()  # Trigger file read for hash computation
    hash_line2 = compute_line_hash(2, "    return 42")

    # Make an edit
    edits = [{"op": "set", "tag": f"2#{hash_line2}", "content": ["    return 100"]}]

    result = edit_file_hashline(str(test_file), edits)

    # Verify
    assert "Successfully applied 1 edit" in result
    new_content = test_file.read_text()
    assert "return 100" in new_content
    assert "return 42" not in new_content


def test_edit_file_hashline_with_mismatch(tmp_path, monkeypatch):
    """Test that hash mismatch is properly reported."""
    test_file = tmp_path / "test.py"
    test_file.write_text("line1\nline2\nline3\n")

    # Disable permission prompts
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    import patchpal.tools.common

    patchpal.tools.common._permission_manager = None

    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", tmp_path)

    from patchpal.tools.file_editing import edit_file_hashline

    # Use wrong hash
    edits = [{"op": "set", "tag": "2#XX", "content": ["changed"]}]

    with pytest.raises(HashlineMismatchError) as exc_info:
        edit_file_hashline(str(test_file), edits)

    error = exc_info.value
    assert "changed since last read" in str(error)
    assert ">>>" in str(error)  # Should show the mismatch marker


"""Test dynamic tool selection based on PATCHPAL_HASHLINE."""


def test_hashline_mode_tool_selection(monkeypatch):
    """Test that PATCHPAL_HASHLINE controls which edit tool is available."""
    # Test with hashline disabled (default)
    monkeypatch.setenv("PATCHPAL_HASHLINE", "false")

    # Need to reload to pick up env changes
    import importlib

    import patchpal.tools.definitions

    importlib.reload(patchpal.tools.definitions)

    tools, functions = patchpal.tools.definitions.get_tools()

    tool_names = [tool["function"]["name"] for tool in tools]

    # Should have edit_file but not edit_file_hashline
    assert "edit_file" in tool_names
    assert "edit_file_hashline" not in tool_names
    assert "edit_file" in functions
    assert "edit_file_hashline" not in functions


def test_hashline_mode_enabled_tool_selection(monkeypatch):
    """Test that edit_file_hashline is available when PATCHPAL_HASHLINE=true."""
    monkeypatch.setenv("PATCHPAL_HASHLINE", "true")

    # Need to reload to pick up env changes
    import importlib

    import patchpal.tools.definitions

    importlib.reload(patchpal.tools.definitions)

    tools, functions = patchpal.tools.definitions.get_tools()

    tool_names = [tool["function"]["name"] for tool in tools]

    # Should have edit_file_hashline but not edit_file
    assert "edit_file_hashline" in tool_names
    assert "edit_file" not in tool_names
    assert "edit_file_hashline" in functions
    assert "edit_file" not in functions


def test_hashline_mode_read_formatting(tmp_path, monkeypatch):
    """Test that PATCHPAL_HASHLINE affects read_file output."""
    test_file = tmp_path / "test.txt"
    test_file.write_text("line1\nline2\nline3\n")

    # Disable permissions
    monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")
    import patchpal.tools.common

    patchpal.tools.common._permission_manager = None
    monkeypatch.setattr("patchpal.tools.common.REPO_ROOT", tmp_path)

    # Test with hashline disabled
    monkeypatch.setenv("PATCHPAL_HASHLINE", "false")
    import importlib

    import patchpal.tools.file_operations

    importlib.reload(patchpal.tools.file_operations)

    from patchpal.tools import read_file

    result = read_file(str(test_file))

    # Should be plain content
    assert result == "line1\nline2\nline3\n"
    assert "#" not in result  # No hash markers

    # Test with hashline enabled
    monkeypatch.setenv("PATCHPAL_HASHLINE", "true")
    importlib.reload(patchpal.tools.file_operations)

    result = read_file(str(test_file))

    # Should have hashline format
    assert "1#" in result
    assert "2#" in result
    assert "3#" in result
    assert ":line1" in result
    assert ":line2" in result
    assert ":line3" in result
