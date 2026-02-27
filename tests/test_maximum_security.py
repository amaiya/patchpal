"""Tests for --maximum-security CLI flag."""

import os
import sys
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def reset_permission_flag():
    """Reset the require-permission-for-all flag and environment variables after each test."""
    yield
    # Cleanup after test - must use os.environ directly, not monkeypatch
    import os

    from patchpal.tools.common import set_require_permission_for_all

    set_require_permission_for_all(False)
    # Clean up environment variables that tests may have set
    os.environ.pop("PATCHPAL_RESTRICT_TO_REPO", None)
    os.environ.pop("PATCHPAL_ENABLE_WEB", None)


def test_maximum_security_flag_sets_all_restrictions(monkeypatch):
    """Test that --maximum-security flag enables all security restrictions."""
    # Mock sys.argv to simulate CLI flag
    test_args = ["patchpal", "--maximum-security"]

    with patch.object(sys, "argv", test_args):
        # Clear any existing env vars
        monkeypatch.delenv("PATCHPAL_RESTRICT_TO_REPO", raising=False)
        monkeypatch.delenv("PATCHPAL_ENABLE_WEB", raising=False)

        # Import after setting argv to capture the flag
        from patchpal.cli.interactive import main
        from patchpal.tools.common import get_require_permission_for_all

        # Mock the interactive loop to exit immediately
        with patch("patchpal.cli.interactive.pt_prompt") as mock_prompt:
            mock_prompt.return_value = "exit"

            # Mock create_agent to avoid actual agent creation
            with patch("patchpal.cli.interactive.create_agent") as mock_create_agent:
                # Mock agent with required attributes
                mock_agent = type("MockAgent", (), {"total_llm_calls": 0, "cumulative_cost": 0})()
                mock_create_agent.return_value = mock_agent

                # Mock console print to avoid output
                with patch("patchpal.cli.interactive.Console"):
                    try:
                        main()
                    except SystemExit:
                        pass  # Expected when user types "exit"

        # Verify all security restrictions are enabled
        assert get_require_permission_for_all() is True, "Permission for all should be enabled"
        assert os.environ.get("PATCHPAL_RESTRICT_TO_REPO") == "true", (
            "Repo restriction should be enabled"
        )
        assert os.environ.get("PATCHPAL_ENABLE_WEB") == "false", "Web access should be disabled"


def test_require_permission_for_all_alone(monkeypatch):
    """Test that --require-permission-for-all works independently without setting other restrictions."""
    test_args = ["patchpal", "--require-permission-for-all"]

    with patch.object(sys, "argv", test_args):
        # Clear env vars
        monkeypatch.delenv("PATCHPAL_RESTRICT_TO_REPO", raising=False)
        monkeypatch.delenv("PATCHPAL_ENABLE_WEB", raising=False)

        from patchpal.cli.interactive import main
        from patchpal.tools.common import get_require_permission_for_all

        with patch("patchpal.cli.interactive.pt_prompt") as mock_prompt:
            mock_prompt.return_value = "exit"

            with patch("patchpal.cli.interactive.create_agent") as mock_create_agent:
                mock_agent = type("MockAgent", (), {"total_llm_calls": 0, "cumulative_cost": 0})()
                mock_create_agent.return_value = mock_agent

                with patch("patchpal.cli.interactive.Console"):
                    try:
                        main()
                    except SystemExit:
                        pass

        # Verify only permission for all is enabled
        assert get_require_permission_for_all() is True, "Permission for all should be enabled"
        # These should NOT be set by --require-permission-for-all alone
        assert os.environ.get("PATCHPAL_RESTRICT_TO_REPO") != "true", (
            "Repo restriction should NOT be enabled"
        )
        assert os.environ.get("PATCHPAL_ENABLE_WEB") != "false", "Web access should NOT be disabled"


def test_maximum_security_display_message(monkeypatch, capsys):
    """Test that --maximum-security shows appropriate security indicator."""
    test_args = ["patchpal", "--maximum-security"]

    with patch.object(sys, "argv", test_args):
        monkeypatch.delenv("PATCHPAL_RESTRICT_TO_REPO", raising=False)
        monkeypatch.delenv("PATCHPAL_ENABLE_WEB", raising=False)

        from patchpal.cli.interactive import main

        with patch("patchpal.cli.interactive.pt_prompt") as mock_prompt:
            mock_prompt.return_value = "exit"

            with patch("patchpal.cli.interactive.create_agent") as mock_create_agent:
                mock_agent = type("MockAgent", (), {"total_llm_calls": 0, "cumulative_cost": 0})()
                mock_create_agent.return_value = mock_agent

                with patch("patchpal.cli.interactive.Console"):
                    try:
                        main()
                    except SystemExit:
                        pass

        # Check output for security indicator
        captured = capsys.readouterr()
        assert "Maximum security mode enabled" in captured.out, (
            "Should show maximum security indicator"
        )
        assert "Permission required for ALL operations" in captured.out
        assert "File access restricted to repository only" in captured.out
        assert "Web access disabled" in captured.out
