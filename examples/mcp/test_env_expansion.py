#!/usr/bin/env python3
"""Test environment variable expansion in MCP configuration.

This script tests the env var expansion feature without requiring
an actual MCP server connection.

Usage:
    python examples/mcp/test_env_expansion.py
"""

import os
import sys
from pathlib import Path

# Add patchpal to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from patchpal.tools.mcp import _expand_env_var, _expand_env_vars_in_config


def test_basic_expansion():
    """Test basic ${VAR} expansion."""
    print("Test 1: Basic expansion")

    os.environ["TEST_VAR"] = "test-value"
    result = _expand_env_var("prefix-${TEST_VAR}-suffix")
    assert result == "prefix-test-value-suffix", (
        f"Expected 'prefix-test-value-suffix', got '{result}'"
    )
    print("  ✓ Basic expansion works")


def test_default_value():
    """Test ${VAR:-default} expansion."""
    print("\nTest 2: Default value expansion")

    # Unset variable should use default
    if "UNSET_VAR" in os.environ:
        del os.environ["UNSET_VAR"]
    result = _expand_env_var("${UNSET_VAR:-default-value}")
    assert result == "default-value", f"Expected 'default-value', got '{result}'"
    print("  ✓ Default value works when variable is unset")

    # Set variable should override default
    os.environ["SET_VAR"] = "actual-value"
    result = _expand_env_var("${SET_VAR:-default-value}")
    assert result == "actual-value", f"Expected 'actual-value', got '{result}'"
    print("  ✓ Actual value overrides default when set")


def test_missing_var():
    """Test that missing required variable raises error."""
    print("\nTest 3: Missing required variable")

    if "MISSING_VAR" in os.environ:
        del os.environ["MISSING_VAR"]

    try:
        _expand_env_var("${MISSING_VAR}")
        print("  ✗ Should have raised ValueError")
        sys.exit(1)
    except ValueError as e:
        assert "not set and has no default" in str(e)
        print("  ✓ Correctly raises error for missing variable")


def test_config_expansion():
    """Test expansion in nested config structures."""
    print("\nTest 4: Config structure expansion")

    os.environ["API_URL"] = "https://api.example.com"
    os.environ["API_TOKEN"] = "secret-token"

    config = {
        "type": "remote",
        "url": "${API_URL}/mcp",
        "headers": {
            "Authorization": "Bearer ${API_TOKEN}",
            "X-Custom": "${UNSET_VAR:-default-header}",
        },
        "environment": {"KEY": "${API_TOKEN}"},
    }

    expanded = _expand_env_vars_in_config(config)

    assert expanded["url"] == "https://api.example.com/mcp", (
        f"URL expansion failed: {expanded['url']}"
    )
    assert expanded["headers"]["Authorization"] == "Bearer secret-token", "Header expansion failed"
    assert expanded["headers"]["X-Custom"] == "default-header", "Default value in header failed"
    assert expanded["environment"]["KEY"] == "secret-token", "Environment var expansion failed"

    print("  ✓ Config structure expansion works")


def test_list_expansion():
    """Test expansion in lists (e.g., command args)."""
    print("\nTest 5: List expansion")

    os.environ["PYTHON_PATH"] = "/usr/bin/python3"
    os.environ["SCRIPT_PATH"] = "/opt/scripts/server.py"

    config = {"command": ["${PYTHON_PATH}", "${SCRIPT_PATH}", "--port", "${PORT:-8080}"]}

    expanded = _expand_env_vars_in_config(config)

    assert expanded["command"][0] == "/usr/bin/python3", "Command expansion failed"
    assert expanded["command"][1] == "/opt/scripts/server.py", "Arg expansion failed"
    assert expanded["command"][3] == "8080", "Default port expansion failed"

    print("  ✓ List expansion works")


def test_no_expansion_when_no_vars():
    """Test that strings without variables pass through unchanged."""
    print("\nTest 6: Pass-through without variables")

    result = _expand_env_var("https://api.example.com/mcp")
    assert result == "https://api.example.com/mcp", f"Plain string was modified: {result}"

    config = {"url": "https://api.example.com", "port": 8080, "enabled": True, "name": None}
    expanded = _expand_env_vars_in_config(config)

    assert expanded == config, "Config was modified when it shouldn't be"
    print("  ✓ Strings without variables pass through unchanged")


def main():
    """Run all tests."""
    print("Testing environment variable expansion\n" + "=" * 50)

    try:
        test_basic_expansion()
        test_default_value()
        test_missing_var()
        test_config_expansion()
        test_list_expansion()
        test_no_expansion_when_no_vars()

        print("\n" + "=" * 50)
        print("✓ All tests passed!")
        return 0

    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        return 1
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
