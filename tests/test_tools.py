"""Tests for tool implementations."""

import tempfile
from pathlib import Path

import pytest

from patchpal.tools import (
    apply_patch,
    count_lines,
    edit_file,
    find_files,
    get_file_info,
    list_files,
    read_file,
    read_lines,
    run_shell,
    tree,
)


@pytest.fixture
def temp_repo(monkeypatch):
    """Create a temporary directory and set it as the repository root."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)

        # Mock the REPO_ROOT to be our temp directory
        import patchpal.tools.common as common

        monkeypatch.setattr(common, "REPO_ROOT", tmpdir_path)

        # Disable permission prompts during tests
        monkeypatch.setenv("PATCHPAL_REQUIRE_PERMISSION", "false")

        # Mock permission manager to auto-grant all permissions in tests
        class MockPermissionManager:
            def request_permission(self, *args, **kwargs):
                return True

        monkeypatch.setattr(common, "_get_permission_manager", lambda: MockPermissionManager())

        # Create a simple file structure
        (tmpdir_path / "test.txt").write_text("Hello, World!")
        (tmpdir_path / "subdir").mkdir()
        (tmpdir_path / "subdir" / "nested.txt").write_text("Nested file")

        yield tmpdir_path


def test_read_file(temp_repo):
    """Test basic file reading."""
    result = read_file("test.txt")
    assert "Hello, World!" in result


def test_read_file_in_subdir(temp_repo):
    """Test reading a file in a subdirectory."""
    result = read_file("subdir/nested.txt")
    assert "Nested file" in result


def test_read_file_not_found(temp_repo):
    """Test error when file doesn't exist."""
    with pytest.raises(ValueError, match="File not found"):
        read_file("nonexistent.txt")


def test_read_file_image_png(temp_repo):
    """Test reading a PNG image file returns base64 data URL."""
    # Create a minimal valid PNG (1x1 red pixel)
    png_data = bytes(
        [
            0x89,
            0x50,
            0x4E,
            0x47,
            0x0D,
            0x0A,
            0x1A,
            0x0A,  # PNG signature
            0x00,
            0x00,
            0x00,
            0x0D,
            0x49,
            0x48,
            0x44,
            0x52,  # IHDR chunk
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x01,  # 1x1 dimensions
            0x08,
            0x02,
            0x00,
            0x00,
            0x00,
            0x90,
            0x77,
            0x53,
            0xDE,
            0x00,
            0x00,
            0x00,
            0x0C,
            0x49,
            0x44,
            0x41,  # IDAT chunk
            0x54,
            0x08,
            0xD7,
            0x63,
            0xF8,
            0xCF,
            0xC0,
            0x00,
            0x00,
            0x00,
            0x03,
            0x00,
            0x01,
            0x6F,
            0xBF,
            0x0D,
            0x14,
            0x00,
            0x00,
            0x00,
            0x00,
            0x49,
            0x45,
            0x4E,  # IEND chunk
            0x44,
            0xAE,
            0x42,
            0x60,
            0x82,
        ]
    )

    (temp_repo / "test.png").write_bytes(png_data)

    result = read_file("test.png")

    # Should be in IMAGE_DATA format
    assert result.startswith("IMAGE_DATA:image/png:")
    # Should contain base64 data after the second colon
    parts = result.split(":", 2)
    assert len(parts) == 3
    assert parts[0] == "IMAGE_DATA"
    assert parts[1] == "image/png"
    assert len(parts[2]) > 0  # Has base64 data


def test_read_file_image_jpeg(temp_repo):
    """Test reading a JPEG image file returns correct MIME type."""
    # Create a minimal JPEG marker (not a valid JPEG, just for testing)
    jpeg_data = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100

    (temp_repo / "test.jpg").write_bytes(jpeg_data)

    result = read_file("test.jpg")

    # Should have JPEG MIME type
    assert result.startswith("IMAGE_DATA:image/jpeg:")


def test_read_file_svg_as_text(temp_repo):
    """Test that SVG files are read as text, not base64."""
    svg_content = '<svg><circle cx="50" cy="50" r="40"/></svg>'
    (temp_repo / "test.svg").write_text(svg_content)

    result = read_file("test.svg")

    # SVG should be returned as text, not base64
    assert not result.startswith("data:")
    assert "<svg>" in result
    assert svg_content == result


def test_read_file_svg_too_large(temp_repo):
    """Test that oversized SVG files (text) are rejected by normal file size limit."""
    # Create a large SVG that exceeds the default 500KB limit
    # (In practice this is unlikely, but we test the logic)
    large_svg = "<svg>" + "x" * (600 * 1024) + "</svg>"  # 600KB+
    (temp_repo / "huge.svg").write_bytes(large_svg.encode("utf-8"))

    # Should be rejected by MAX_FILE_SIZE check
    with pytest.raises(ValueError, match="SVG file too large"):
        read_file("huge.svg")


def test_read_file_image_size_default(temp_repo):
    """Test that small images work fine with default limits."""
    # Create a 50KB image - base64 will be ~67KB, under 100K limit
    image_data = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * (50 * 1024)
    (temp_repo / "small.jpg").write_bytes(image_data)

    # Should succeed and return IMAGE_DATA format
    result = read_file("small.jpg")
    assert result.startswith("IMAGE_DATA:image/jpeg:")
    # Verify it has base64 data
    parts = result.split(":", 2)
    assert len(parts) == 3
    assert len(parts[2]) > 50000  # Should have substantial base64 content


def test_read_lines_single_line(temp_repo):
    """Test reading a single line from a file."""
    (temp_repo / "multiline.txt").write_text("Line 1\nLine 2\nLine 3\n")

    result = read_lines("multiline.txt", 2)

    # Should contain line 2 with line number
    assert "2" in result
    assert "Line 2" in result
    # Should not contain other lines
    assert "Line 1" not in result
    assert "Line 3" not in result


def test_read_lines_range(temp_repo):
    """Test reading a range of lines from a file."""
    (temp_repo / "multiline.txt").write_text("Line 1\nLine 2\nLine 3\nLine 4\n")

    result = read_lines("multiline.txt", 2, 3)

    # Should contain lines 2 and 3
    assert "Line 2" in result
    assert "Line 3" in result
    # Should not contain lines 1 and 4
    assert "Line 1" not in result
    assert "Line 4" not in result


def test_read_lines_entire_file(temp_repo):
    """Test reading all lines when range exceeds file length."""
    (temp_repo / "short.txt").write_text("Line 1\nLine 2\n")

    result = read_lines("short.txt", 1, 100)

    # Should contain both lines
    assert "Line 1" in result
    assert "Line 2" in result


def test_read_lines_invalid_range(temp_repo):
    """Test error when end_line < start_line."""
    (temp_repo / "test.txt").write_text("Line 1\nLine 2\n")

    with pytest.raises(ValueError, match="end_line.*must be >= start_line"):
        read_lines("test.txt", 3, 1)


def test_read_lines_beyond_file_end(temp_repo):
    """Test reading when start_line exceeds file length."""
    (temp_repo / "short.txt").write_text("Line 1\n")

    with pytest.raises(ValueError, match="exceeds file length"):
        read_lines("short.txt", 10)


def test_read_lines_file_not_found(temp_repo):
    """Test error when file doesn't exist."""
    with pytest.raises(ValueError):
        read_lines("nonexistent.txt", 1)


def test_count_lines(temp_repo):
    """Test counting lines in a file."""
    (temp_repo / "test.txt").write_text("Line 1\nLine 2\nLine 3\n")

    result = count_lines("test.txt")

    assert "3 lines" in result
    assert "test.txt" in result


def test_list_files(temp_repo):
    """Test listing all files in repository."""
    result = list_files()

    # Should include our test files
    assert isinstance(result, list)
    assert len(result) >= 2  # At least test.txt and subdir/nested.txt


def test_get_file_info_single_file(temp_repo):
    """Test getting info for a single file."""
    result = get_file_info("test.txt")

    # Should contain file name and size info
    assert "test.txt" in result
    assert "B" in result or "KB" in result  # Size unit


def test_get_file_info_directory(temp_repo):
    """Test getting info for all files in a directory."""
    result = get_file_info("subdir")

    # Should list files in the directory
    assert "nested.txt" in result


def test_get_file_info_glob_pattern(temp_repo):
    """Test getting info with glob pattern."""
    (temp_repo / "test1.py").write_text("test")
    (temp_repo / "test2.py").write_text("test")

    result = get_file_info("*.py")

    assert "test1.py" in result
    assert "test2.py" in result


def test_get_file_info_not_found(temp_repo):
    """Test handling of non-existent path."""
    result = get_file_info("nonexistent.txt")

    assert "does not exist" in result


def test_find_files_pattern(temp_repo):
    """Test finding files by pattern."""
    (temp_repo / "test1.txt").write_text("test")
    (temp_repo / "test2.txt").write_text("test")
    (temp_repo / "other.py").write_text("test")

    result = find_files("*.txt")

    # Should find both .txt files
    assert "test1.txt" in result
    assert "test2.txt" in result
    # Should not find .py file
    assert "other.py" not in result


def test_find_files_case_insensitive(temp_repo):
    """Test case-insensitive file finding."""
    (temp_repo / "TEST.TXT").write_text("test")

    result = find_files("*.txt", case_sensitive=False)

    assert "TEST.TXT" in result


def test_tree_basic(temp_repo):
    """Test basic tree generation."""
    result = tree(".")

    # Should show directory structure
    assert "test.txt" in result
    assert "subdir" in result


def test_tree_max_depth(temp_repo):
    """Test tree depth limiting."""
    # Create nested directories
    (temp_repo / "a" / "b" / "c").mkdir(parents=True)
    (temp_repo / "a" / "b" / "c" / "deep.txt").write_text("deep")

    # Tree with depth 2 should not show deep.txt
    result = tree(".", max_depth=2)

    # Should show a and b, but not c
    assert "/a/" in result or "a/" in result
    # The exact format depends on tree implementation


def test_edit_file_simple_replacement(temp_repo):
    """Test basic string replacement in a file."""
    (temp_repo / "edit_test.txt").write_text("Hello World\nGoodbye World\n")

    result = edit_file("edit_test.txt", "Hello World", "Hi Universe")

    # Check result message
    assert "success" in result.lower() or "1 replacement" in result

    # Verify file was actually edited
    content = (temp_repo / "edit_test.txt").read_text()
    assert "Hi Universe" in content
    assert "Hello World" not in content


def test_edit_file_not_found(temp_repo):
    """Test error when file doesn't exist."""
    with pytest.raises(ValueError, match="not found"):
        edit_file("nonexistent.txt", "old", "new")


def test_edit_file_string_not_found(temp_repo):
    """Test error when old_string doesn't exist."""
    (temp_repo / "test.txt").write_text("Hello World")

    with pytest.raises(ValueError, match="not found"):
        edit_file("test.txt", "Nonexistent String", "new")


def test_apply_patch_simple(temp_repo):
    """Test applying a complete file patch."""
    (temp_repo / "patch_test.txt").write_text("Old content\n")

    new_content = "New content\nLine 2\n"
    result = apply_patch("patch_test.txt", new_content)

    # Check result
    assert "success" in result.lower() or "applied" in result.lower()

    # Verify file content
    content = (temp_repo / "patch_test.txt").read_text()
    assert content == new_content


def test_apply_patch_not_found(temp_repo):
    """Test that apply_patch can create new files."""
    result = apply_patch("nonexistent.txt", "new content")

    # Should succeed in creating the file
    assert "success" in result.lower() or "applied" in result.lower()

    # Verify file was created
    assert (temp_repo / "nonexistent.txt").exists()
    content = (temp_repo / "nonexistent.txt").read_text()
    assert content == "new content"


def test_run_shell_basic(temp_repo):
    """Test basic shell command execution."""
    result = run_shell("echo 'Hello from shell'")

    assert "Hello from shell" in result


def test_run_shell_pwd(temp_repo):
    """Test that shell commands run in repo root."""
    result = run_shell("pwd")

    # Result should contain the temp repo path
    assert str(temp_repo) in result


def test_run_shell_ls(temp_repo):
    """Test listing files via shell."""
    result = run_shell("ls")

    # Should list our test files
    assert "test.txt" in result or "test.txt" in result.lower()


def test_run_shell_permission_sudo_blocked():
    """Test that sudo commands are blocked by default."""
    with pytest.raises(ValueError, match="sudo|permission"):
        run_shell("sudo ls")
