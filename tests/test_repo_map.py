"""Tests for the repository map tool."""

from patchpal.tools.repo_map import clear_repo_map_cache, get_repo_map, get_repo_map_stats


def test_get_repo_map_basic():
    """Test basic repository map generation."""
    result = get_repo_map(max_files=10)

    # Should return a string
    assert isinstance(result, str)

    # Should contain "Repository Map"
    assert "Repository Map" in result

    # Should contain some Python files (we know patchpal has .py files)
    assert ".py" in result or "files analyzed" in result


def test_get_repo_map_with_include_patterns():
    """Test repository map with include patterns."""
    result = get_repo_map(max_files=50, include_patterns=["*.py"])

    assert isinstance(result, str)
    assert "Repository Map" in result

    # Should only show Python files
    if "patchpal" in result:  # If it found any files
        # All file paths should be .py
        lines = result.split("\n")
        file_lines = [line for line in lines if line.endswith(":") and not line.startswith(" ")]
        # Most should be .py files
        py_files = [line for line in file_lines if ".py:" in line]
        assert len(py_files) > 0


def test_get_repo_map_with_exclude_patterns():
    """Test repository map with exclude patterns."""
    result = get_repo_map(max_files=50, exclude_patterns=["*test*", "*__pycache__*"])

    assert isinstance(result, str)
    assert "Repository Map" in result

    # Should not contain test files
    assert "test_" not in result.lower() or "Skipped" in result


def test_get_repo_map_with_max_files():
    """Test repository map respects max_files limit."""
    result = get_repo_map(max_files=5)

    assert isinstance(result, str)
    assert "Repository Map" in result

    # Count how many files are shown
    lines = result.split("\n")
    file_count = sum(
        1
        for line in lines
        if line and not line.startswith(" ") and line.endswith(":") and "/" in line
    )

    # Should show at most 5 files (plus some might be in the header)
    assert file_count <= 6  # Allow for some header lines


def test_get_repo_map_caching():
    """Test that repository map caching works."""
    # Clear cache first
    clear_repo_map_cache()

    # First call should populate cache
    result1 = get_repo_map(max_files=10)
    stats1 = get_repo_map_stats()

    assert stats1["cached_files"] > 0

    # Second call should use cache
    result2 = get_repo_map(max_files=10)
    stats2 = get_repo_map_stats()

    # Cache size should be the same or larger
    assert stats2["cached_files"] >= stats1["cached_files"]

    # Results should be identical (cache hit)
    assert result1 == result2


def test_get_repo_map_shows_structure():
    """Test that repo map shows code structure."""
    result = get_repo_map(max_files=50, include_patterns=["patchpal/tools/*.py"])

    assert isinstance(result, str)

    # Should show some structure (classes, functions, lines)
    # Look for common patterns in the output
    has_structure = (
        "Line" in result
        or "class" in result.lower()
        or "def" in result.lower()
        or "function" in result.lower()
    )

    # If we found any files, they should have structure
    if "patchpal/tools" in result:
        assert has_structure or "files analyzed, showing 0" in result


def test_clear_repo_map_cache():
    """Test clearing the repository map cache."""
    # Populate cache
    get_repo_map(max_files=5)
    stats_before = get_repo_map_stats()
    assert stats_before["cached_files"] > 0

    # Clear cache
    clear_repo_map_cache()
    stats_after = get_repo_map_stats()

    # Cache should be empty
    assert stats_after["cached_files"] == 0


def test_get_repo_map_stats():
    """Test repository map statistics."""
    clear_repo_map_cache()

    stats = get_repo_map_stats()

    # Should return a dict with expected keys
    assert isinstance(stats, dict)
    assert "cached_files" in stats
    assert "last_scan" in stats
    assert "cache_age" in stats

    # After clearing, cache should be empty
    assert stats["cached_files"] == 0


def test_get_repo_map_focus_files():
    """Test repository map with focus files."""
    # Get a basic map first to find some files
    basic_result = get_repo_map(max_files=5, include_patterns=["*.py"])

    # Extract a file name from the result
    lines = basic_result.split("\n")
    file_lines = [line.strip() for line in lines if line.endswith(":") and ".py:" in line]

    if file_lines:
        # Get first file (without the colon)
        focus_file = file_lines[0].rstrip(":")

        # Request map with this as a focus file
        focused_result = get_repo_map(max_files=50, focus_files=[focus_file])

        # The focus file should appear in the output
        assert focus_file in focused_result
