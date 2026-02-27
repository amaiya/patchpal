"""Test that config variables are truly dynamic (read from env vars dynamically)."""

import os


def test_config_is_dynamic():
    """Test that config properties read environment variables dynamically."""
    from patchpal.config import config

    # Set environment variable
    os.environ["PATCHPAL_MAX_FILE_SIZE"] = "123456"

    # Config should read the new value immediately (no module reload needed)
    assert config.MAX_FILE_SIZE == 123456

    # Change it again
    os.environ["PATCHPAL_MAX_FILE_SIZE"] = "999999"

    # Should reflect the change immediately
    assert config.MAX_FILE_SIZE == 999999

    # Clean up
    del os.environ["PATCHPAL_MAX_FILE_SIZE"]


def test_config_boolean_properties_dynamic():
    """Test that boolean config properties are dynamic."""
    from patchpal.config import config

    # Test READ_ONLY
    os.environ["PATCHPAL_READ_ONLY"] = "true"
    assert config.READ_ONLY is True

    os.environ["PATCHPAL_READ_ONLY"] = "false"
    assert config.READ_ONLY is False

    # Test ALLOW_SENSITIVE
    os.environ["PATCHPAL_ALLOW_SENSITIVE"] = "true"
    assert config.ALLOW_SENSITIVE is True

    os.environ["PATCHPAL_ALLOW_SENSITIVE"] = "false"
    assert config.ALLOW_SENSITIVE is False

    # Clean up
    del os.environ["PATCHPAL_READ_ONLY"]
    del os.environ["PATCHPAL_ALLOW_SENSITIVE"]


def test_tools_use_config_dynamically():
    """Test that tool modules read config dynamically."""
    import tempfile
    from pathlib import Path

    # Create a small test file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
        f.write("x" * 2000)  # 2KB file
        test_file = Path(f.name)

    try:
        # Set a very small file size limit
        os.environ["PATCHPAL_MAX_FILE_SIZE"] = "1000"
        os.environ["PATCHPAL_REQUIRE_PERMISSION"] = "false"

        from patchpal.tools import read_file

        # Should fail because file is 2KB but limit is 1KB
        try:
            read_file(str(test_file))
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "too large" in str(e)

        # Now increase the limit
        os.environ["PATCHPAL_MAX_FILE_SIZE"] = "5000"

        # Should work now without module reload
        content = read_file(str(test_file))
        assert len(content) == 2000

    finally:
        # Clean up
        test_file.unlink()
        del os.environ["PATCHPAL_MAX_FILE_SIZE"]
        del os.environ["PATCHPAL_REQUIRE_PERMISSION"]
