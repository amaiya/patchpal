"""Test MCP configuration loading and merging."""

import json
from pathlib import Path

import pytest

from patchpal.tools.mcp import _load_mcp_config


def test_load_mcp_config_explicit_path(tmp_path):
    """Test loading config from explicit path."""
    config_file = tmp_path / "custom_config.json"
    config_data = {
        "mcp": {
            "test_server": {
                "type": "remote",
                "url": "https://example.com",
                "enabled": True,
            }
        }
    }
    config_file.write_text(json.dumps(config_data))

    result = _load_mcp_config(config_file)
    assert result == config_data


def test_load_mcp_config_explicit_path_not_found(tmp_path):
    """Test loading config from non-existent explicit path."""
    config_file = tmp_path / "nonexistent.json"
    result = _load_mcp_config(config_file)
    assert result == {}


def test_load_mcp_config_explicit_path_invalid_json(tmp_path):
    """Test loading config from explicit path with invalid JSON."""
    config_file = tmp_path / "invalid.json"
    config_file.write_text("{invalid json")

    result = _load_mcp_config(config_file)
    assert result == {}


def test_load_mcp_config_global_only(tmp_path, monkeypatch):
    """Test loading config from global location only."""
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)

    config_data = {
        "mcp": {
            "global_server": {
                "type": "remote",
                "url": "https://global.com",
                "enabled": True,
            }
        }
    }
    global_config.write_text(json.dumps(config_data))

    # Change to a directory where no project config exists
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()
    assert result == config_data


def test_load_mcp_config_project_only(tmp_path, monkeypatch):
    """Test loading config from project location only."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)

    config_data = {
        "mcp": {
            "project_server": {
                "type": "local",
                "command": ["python", "-m", "test_server"],
                "enabled": True,
            }
        }
    }
    project_config.write_text(json.dumps(config_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake_home")

    result = _load_mcp_config()
    assert result == config_data


def test_load_mcp_config_merge_different_servers(tmp_path, monkeypatch):
    """Test merging configs with different server names."""
    # Create global config
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {
            "global_server": {
                "type": "remote",
                "url": "https://global.com",
                "enabled": True,
            }
        }
    }
    global_config.write_text(json.dumps(global_data))

    # Create project config
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {
        "mcp": {
            "project_server": {
                "type": "local",
                "command": ["python", "-m", "test_server"],
                "enabled": True,
            }
        }
    }
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Should have both servers
    assert "global_server" in result["mcp"]
    assert "project_server" in result["mcp"]
    assert result["mcp"]["global_server"]["url"] == "https://global.com"
    assert result["mcp"]["project_server"]["command"] == ["python", "-m", "test_server"]


def test_load_mcp_config_merge_override_server(tmp_path, monkeypatch):
    """Test project config overriding global config for same server name."""
    # Create global config
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {
            "shared_server": {
                "type": "remote",
                "url": "https://global.com",
                "enabled": True,
            }
        }
    }
    global_config.write_text(json.dumps(global_data))

    # Create project config with same server name
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {
        "mcp": {
            "shared_server": {
                "type": "remote",
                "url": "https://project-override.com",
                "enabled": True,
                "headers": {"Authorization": "Bearer token"},
            }
        }
    }
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Project config should override global
    assert result["mcp"]["shared_server"]["url"] == "https://project-override.com"
    assert result["mcp"]["shared_server"]["headers"] == {"Authorization": "Bearer token"}


def test_load_mcp_config_disable_global_server(tmp_path, monkeypatch):
    """Test project config disabling a global server."""
    # Create global config
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {
            "global_server": {
                "type": "remote",
                "url": "https://global.com",
                "enabled": True,
            }
        }
    }
    global_config.write_text(json.dumps(global_data))

    # Create project config that disables the server
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {
        "mcp": {
            "global_server": {
                "enabled": False,
            }
        }
    }
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Server should be disabled
    assert result["mcp"]["global_server"]["enabled"] is False
    # Note: In a full override, only "enabled" key is present from project config


def test_load_mcp_config_merge_other_keys(tmp_path, monkeypatch):
    """Test merging non-mcp config keys (for future extensibility)."""
    # Create global config with multiple keys
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {"server1": {"type": "remote", "url": "https://global.com"}},
        "defaults": {"model": "gpt-4"},
        "global_setting": "value1",
    }
    global_config.write_text(json.dumps(global_data))

    # Create project config with overlapping keys
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {
        "mcp": {"server2": {"type": "local", "command": ["test"]}},
        "defaults": {"model": "claude-3"},
        "project_setting": "value2",
    }
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # MCP servers should be merged
    assert "server1" in result["mcp"]
    assert "server2" in result["mcp"]

    # Other keys should be overridden by project config
    assert result["defaults"]["model"] == "claude-3"
    assert result["project_setting"] == "value2"
    assert "global_setting" in result  # Still present from global


def test_load_mcp_config_global_invalid_json(tmp_path, monkeypatch):
    """Test handling invalid JSON in global config."""
    # Create invalid global config
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_config.write_text("{invalid json")

    # Create valid project config
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {
        "mcp": {
            "project_server": {
                "type": "local",
                "command": ["test"],
            }
        }
    }
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Should still load project config despite global error
    assert result == project_data


def test_load_mcp_config_project_invalid_json(tmp_path, monkeypatch):
    """Test handling invalid JSON in project config."""
    # Create valid global config
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {
            "global_server": {
                "type": "remote",
                "url": "https://global.com",
            }
        }
    }
    global_config.write_text(json.dumps(global_data))

    # Create invalid project config
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_config.write_text("{invalid json")

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Should still have global config despite project error
    assert result == global_data


def test_load_mcp_config_no_configs(tmp_path, monkeypatch):
    """Test loading when no configs exist."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "fake_home")

    result = _load_mcp_config()
    assert result == {}


def test_load_mcp_config_empty_mcp_section(tmp_path, monkeypatch):
    """Test merging when configs have empty or missing mcp sections."""
    # Global has mcp section, project doesn't
    global_config = tmp_path / ".patchpal" / "mcp-config.json"
    global_config.parent.mkdir(parents=True)
    global_data = {
        "mcp": {"server1": {"type": "remote", "url": "https://example.com"}},
        "other_setting": "value",
    }
    global_config.write_text(json.dumps(global_data))

    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_config = project_dir / ".patchpal" / "mcp-config.json"
    project_config.parent.mkdir(parents=True)
    project_data = {"project_setting": "value2"}
    project_config.write_text(json.dumps(project_data))

    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    result = _load_mcp_config()

    # Should have mcp from global and project setting
    assert "server1" in result["mcp"]
    assert result["project_setting"] == "value2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
