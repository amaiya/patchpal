"""Tests for output filtering functionality."""

import os

import pytest


@pytest.fixture(autouse=True)
def reset_output_filter():
    """Reset output filter state before each test."""
    # Ensure filtering is enabled by default
    os.environ["PATCHPAL_FILTER_OUTPUTS"] = "true"

    # Reload module to pick up env var
    import importlib

    import patchpal.tools

    importlib.reload(patchpal.tools)

    yield

    # Cleanup after test
    if "PATCHPAL_FILTER_OUTPUTS" in os.environ:
        del os.environ["PATCHPAL_FILTER_OUTPUTS"]


def test_output_filter_can_be_disabled(monkeypatch):
    """Test that output filtering can be completely disabled."""
    monkeypatch.setenv("PATCHPAL_FILTER_OUTPUTS", "false")

    # Force reload to pick up env var
    import importlib

    import patchpal.tools

    importlib.reload(patchpal.tools)
    from patchpal.tools import OutputFilter

    output = "line1\nline2\nline3"
    result = OutputFilter.filter_output("pytest tests/", output)
    assert result == output, "When disabled, output should be unchanged"


def test_output_filter_non_matching_commands():
    """Test that non-matching commands pass through unchanged."""
    from patchpal.tools import OutputFilter

    output = "some important data\nthat we need\nto see"
    result = OutputFilter.filter_output("ls -la", output)
    assert result == output, "Non-filtered commands should pass through unchanged"


def test_output_filter_empty_output():
    """Test that empty output is handled gracefully."""
    from patchpal.tools import OutputFilter

    result = OutputFilter.filter_output("pytest", "")
    assert result == "", "Empty output should remain empty"


def test_output_filter_all_passing_tests():
    """Test that all-passing test output preserves summary."""
    from patchpal.tools import OutputFilter

    passing_output = """
tests/test_example.py::test_1 PASSED
tests/test_example.py::test_2 PASSED
====== 2 passed in 1.50s ======
"""
    result = OutputFilter.filter_output("pytest tests/", passing_output)
    assert "passed" in result.lower(), "Should keep summary even with no failures"


def test_output_filter_preserves_failures():
    """Test that test failures are preserved with full context."""
    from patchpal.tools import OutputFilter

    failing_output = """
tests/test_example.py::test_1 PASSED
tests/test_example.py::test_2 FAILED
E     AssertionError: expected 2
tests/test_example.py::test_3 PASSED
====== 1 failed, 2 passed in 1.50s ======
"""
    result = OutputFilter.filter_output("pytest tests/", failing_output)

    # Critical assertions - must preserve failure information
    assert "FAILED" in result, "Should keep failure indicator"
    assert "AssertionError" in result, "Should keep error details"
    assert "expected 2" in result, "Should keep error message"
    assert "passed" in result.lower(), "Should keep summary"


def test_output_filter_multiple_failures():
    """Test that multiple failures are all preserved."""
    from patchpal.tools import OutputFilter

    multi_fail = """tests/test_a.py::test_1 PASSED
tests/test_a.py::test_2 FAILED
E     Error in test 2

tests/test_a.py::test_3 FAILED
E     Error in test 3

tests/test_a.py::test_4 PASSED
====== 2 failed, 2 passed in 2.0s ======
"""
    result = OutputFilter.filter_output("pytest", multi_fail)

    # Both failures must be preserved
    assert result.count("FAILED") == 2, "Should keep both failures"
    assert "Error in test 2" in result, "Should keep first error"
    assert "Error in test 3" in result, "Should keep second error"


def test_output_filter_adjacent_failures():
    """Test that failures close together are handled correctly (regression test for bug)."""
    from patchpal.tools import OutputFilter

    # This is the case that exposed the original bug
    adjacent_failures = """tests/test.py::test_1 FAILED
E     First error
tests/test.py::test_2 FAILED
E     Second error
====== 2 failed ======
"""
    result = OutputFilter.filter_output("pytest", adjacent_failures)

    assert result.count("FAILED") == 2, "Both failures must be preserved"
    assert "First error" in result, "First error must be preserved"
    assert "Second error" in result, "Second error must be preserved"


def test_output_filter_truncates_long_output():
    """Test that very long output is truncated appropriately."""
    from patchpal.tools import OutputFilter

    long_output = "\n".join([f"line {i}" for i in range(1000)])
    result = OutputFilter.filter_output("some-command", long_output)

    assert "truncated" in result.lower(), "Long output should show truncation message"
    assert len(result.split("\n")) < 1000, "Long output should be reduced"
    assert len(result.split("\n")) <= 503, "Should truncate to ~500 lines"


def test_output_filter_git_log_short():
    """Test that short git log passes through unchanged."""
    from patchpal.tools import OutputFilter

    git_short = "\n".join([f"commit {i}" for i in range(10)])
    result = OutputFilter.filter_output("git log", git_short)
    assert result == git_short, "Short git log should pass through"


def test_output_filter_git_log_long():
    """Test that long git log is truncated to 50 lines."""
    from patchpal.tools import OutputFilter

    git_long = "\n".join([f"commit line {i}" for i in range(100)])
    result = OutputFilter.filter_output("git log", git_long)

    result_lines = len(result.split("\n"))
    assert result_lines <= 52, f"Long git log should be truncated to ~50 lines, got {result_lines}"
    assert "truncated" in result.lower() or result_lines == 50, "Should show truncation message"


def test_output_filter_should_filter_detection():
    """Test that should_filter correctly identifies commands to filter."""
    from patchpal.tools import OutputFilter

    # Should filter these
    assert OutputFilter.should_filter("pytest tests/")
    assert OutputFilter.should_filter("npm test")
    assert OutputFilter.should_filter("git log")
    assert OutputFilter.should_filter("pip install requests")

    # Should NOT filter these
    assert not OutputFilter.should_filter("ls -la")
    assert not OutputFilter.should_filter("cat file.txt")
    assert not OutputFilter.should_filter("echo hello")


def test_output_filter_preserves_test_errors():
    """Test that test ERRORs (not just FAILUREs) are preserved."""
    from patchpal.tools import OutputFilter

    error_output = """tests/test.py::test_1 PASSED
tests/test.py::test_2 ERROR
E     ImportError: No module named 'missing'
====== 1 error, 1 passed ======
"""
    result = OutputFilter.filter_output("pytest", error_output)

    assert "ERROR" in result, "Should keep ERROR indicator"
    assert "ImportError" in result, "Should keep error details"
    assert "missing" in result, "Should keep module name"


def test_output_filter_npm_test():
    """Test filtering for npm test output."""
    from patchpal.tools import OutputFilter

    npm_output = """
> test
> jest

 PASS  tests/example.test.js
  ✓ should pass (2 ms)
  ✗ should fail (3 ms)

Test Suites: 1 failed, 1 passed, 2 total
Tests:       1 failed, 1 passed, 2 total
"""
    result = OutputFilter.filter_output("npm test", npm_output)

    assert "✗" in result or "fail" in result.lower(), "Should preserve failure"
    assert "Test Suites:" in result or "Tests:" in result, "Should preserve summary"


def test_output_filter_reduction_percentage():
    """Test that filtering achieves significant reduction for verbose output."""
    from patchpal.tools import OutputFilter

    # Create verbose test output with mostly passing tests
    verbose_output = "\n".join(
        [f"tests/test_{i}.py::test_{j} PASSED" for i in range(10) for j in range(10)]
        + [
            "tests/test_fail.py::test_fail FAILED",
            "E     AssertionError",
            "====== 1 failed, 99 passed ======",
        ]
    )

    result = OutputFilter.filter_output("pytest", verbose_output)

    original_lines = len(verbose_output.split("\n"))
    filtered_lines = len(result.split("\n"))
    reduction = (1 - filtered_lines / original_lines) * 100

    # Should achieve significant reduction (at least 50% for this case)
    assert reduction >= 50, f"Expected at least 50% reduction, got {reduction:.1f}%"

    # But must still preserve the failure
    assert "FAILED" in result
    assert "AssertionError" in result
