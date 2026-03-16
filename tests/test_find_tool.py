#!/usr/bin/env python3
"""Tests for the find tool - both glob pattern matching and ls-like listing."""

import time

import pytest


@pytest.fixture
def test_dir(tmp_path):
    """Create a temporary directory structure for testing."""
    # Create directory structure
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".git").mkdir()
    (tmp_path / "docs").mkdir()

    # Create Python files
    (tmp_path / "src" / "main.py").write_text("print('main')")
    (tmp_path / "src" / "utils.py").write_text("print('utils')")
    (tmp_path / "tests" / "test_main.py").write_text("def test(): pass")

    # Create other files
    (tmp_path / "README.md").write_text("# README")
    (tmp_path / "setup.py").write_text("setup()")
    (tmp_path / "docs" / "guide.md").write_text("# Guide")

    # Create .gitignore
    (tmp_path / ".gitignore").write_text("*.pyc\n__pycache__/\n.git/\n")

    # Create ignored files (should be filtered out)
    (tmp_path / "test.pyc").write_text("compiled")
    (tmp_path / ".git" / "config").write_text("git config")

    return tmp_path


def test_find_without_pattern_lists_all_files(test_dir, monkeypatch):
    """Test that find() without pattern lists all files (ls-like behavior)."""
    # Patch REPO_ROOT before importing find
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Call find without pattern (should list all files)
    result = find()

    # Verify it returns multiple files
    files = result.split("\n")
    assert len(files) > 0

    # Should include Python files
    assert any("main.py" in f for f in files), f"main.py not found in {files}"
    assert any("utils.py" in f for f in files), f"utils.py not found in {files}"
    assert any("test_main.py" in f for f in files), f"test_main.py not found in {files}"

    # Should include markdown files
    assert any("README.md" in f for f in files), f"README.md not found in {files}"
    assert any("guide.md" in f for f in files), f"guide.md not found in {files}"

    # Should include setup.py
    assert any("setup.py" in f for f in files), f"setup.py not found in {files}"

    print(f"✓ find() without pattern listed {len(files)} files")


def test_find_with_path_lists_directory_files(test_dir, monkeypatch):
    """Test that find(path='dir') lists all files in directory (ls dir behavior)."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # List files in src directory
    result = find(path="src")
    files = result.split("\n")

    # Should only include files from src/
    assert any("main.py" in f for f in files), f"main.py not in {files}"
    assert any("utils.py" in f for f in files), f"utils.py not in {files}"

    # Should NOT include files from other directories
    assert not any("test_main.py" in f for f in files), f"test_main.py should not be in {files}"
    assert not any("README.md" in f for f in files), f"README.md should not be in {files}"

    print("✓ find(path='src') listed files only in src directory")


def test_find_with_glob_pattern(test_dir, monkeypatch):
    """Test that find('*.py') finds all Python files (glob behavior)."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Find all Python files
    result = find("*.py")
    files = result.split("\n")

    # Should find Python files
    assert any("main.py" in f for f in files), f"main.py not found in {files}"
    assert any("utils.py" in f for f in files), f"utils.py not found in {files}"
    assert any("test_main.py" in f for f in files), f"test_main.py not found in {files}"
    assert any("setup.py" in f for f in files), f"setup.py not found in {files}"

    # Should NOT find markdown files
    assert not any(".md" in f for f in files), f"Found .md file in {files}"

    print(f"✓ find('*.py') found {len(files)} Python files")


def test_find_with_recursive_glob_pattern(test_dir, monkeypatch):
    """Test that find('**/*.md') finds markdown files recursively."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Find all markdown files recursively
    result = find("**/*.md")
    files = result.split("\n")

    # Should find markdown files in root and subdirectories
    assert any("README.md" in f for f in files), f"README.md not found in {files}"
    assert any("guide.md" in f for f in files), f"guide.md not found in {files}"

    # Should NOT find Python files
    assert not any(".py" in f for f in files), f"Found .py file in {files}"

    print(f"✓ find('**/*.md') found {len(files)} markdown files")


def test_find_with_pattern_and_path(test_dir, monkeypatch):
    """Test that find('*.py', path='src') combines pattern and path."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Find Python files only in src directory
    result = find("*.py", path="src")
    files = result.split("\n")

    # Should find Python files in src
    assert any("main.py" in f for f in files), f"main.py not found in {files}"
    assert any("utils.py" in f for f in files), f"utils.py not found in {files}"

    # Should NOT find test_main.py (in tests directory)
    assert not any("test_main.py" in f for f in files), f"test_main.py should not be in {files}"
    # Should NOT find setup.py (in root)
    assert not any("setup.py" in f for f in files), f"setup.py should not be in {files}"

    print("✓ find('*.py', path='src') found Python files only in src/")


def test_find_respects_gitignore(test_dir, monkeypatch):
    """Test that find respects .gitignore patterns."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Find all files
    result = find()
    files = result.split("\n")

    # Should NOT include .pyc files (ignored)
    assert not any(".pyc" in f for f in files), f"Found .pyc file in {files}"

    # Should NOT include .git directory files (ignored)
    assert not any(".git/config" in f or ".git\\config" in f for f in files), (
        f"Found .git/config in {files}"
    )

    print("✓ find() respects .gitignore patterns")


def test_find_sorts_by_modification_time(test_dir, monkeypatch):
    """Test that find returns files sorted by modification time (newest first)."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Create files with different modification times in root
    file1 = test_dir / "zzz_old_file.dat"
    file1.write_text("old")
    time.sleep(0.3)  # Increase sleep time for more reliable test

    file2 = test_dir / "zzz_new_file.dat"
    file2.write_text("new")

    # Get modification times
    mtime1 = file1.stat().st_mtime
    mtime2 = file2.stat().st_mtime

    # Newer file should have later mtime
    assert mtime2 > mtime1

    # Find all .dat files recursively
    result = find("**/*.dat")
    files = result.split("\n")

    # Should have exactly 2 files (our test files)
    assert len(files) == 2, f"Expected 2 files, got {len(files)}: {files}"

    # new_file should appear before old_file (sorted by mtime descending)
    assert "zzz_new_file.dat" in files[0], f"Expected zzz_new_file.dat first, got {files}"
    assert "zzz_old_file.dat" in files[1], f"Expected zzz_old_file.dat second, got {files}"

    print("✓ find() sorts by modification time (newest first)")


def test_find_with_nonexistent_path(test_dir, monkeypatch):
    """Test that find raises error for non-existent path."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Try to find in non-existent directory
    with pytest.raises(ValueError, match="Path not found"):
        find(path="nonexistent")

    print("✓ find() raises error for non-existent path")


def test_find_no_matches_returns_message(test_dir, monkeypatch):
    """Test that find returns message when no files match pattern."""
    import patchpal.tools.find_tool

    monkeypatch.setattr(patchpal.tools.find_tool, "REPO_ROOT", test_dir)
    from patchpal.tools.find_tool import find

    # Search for files that don't exist
    result = find("*.nonexistent")

    assert "No files found" in result

    print("✓ find() returns message when no matches found")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
