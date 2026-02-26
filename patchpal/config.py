"""Centralized configuration management for PatchPal.

All environment variables are read here in a single location.
This provides:
- Single source of truth for configuration
- Type safety with explicit types
- Easy discoverability of all configuration options
- Simplified testing (mock the config object instead of env vars)

Usage:
    from patchpal.config import config

    if config.ENABLE_WEB:
        # Web tools are enabled
        ...

Note: This module provides centralized access to all PATCHPAL_* environment variables.
      Properties read env vars dynamically, so tests can use monkeypatch without reloading modules.
"""

import os
from typing import Optional


def _get_env_bool(env_var: str, default: str = "false") -> bool:
    """Parse environment variable as boolean.

    Internal helper function to avoid circular imports.

    Args:
        env_var: Environment variable name
        default: Default value if not set (typically "true" or "false")

    Returns:
        True if the environment variable is set to a truthy value ("true", "1", or "yes"),
        False otherwise
    """
    return os.getenv(env_var, default).lower() in ("true", "1", "yes")


class Config:
    """PatchPal configuration loaded from environment variables.

    Uses properties to read env vars dynamically, making it test-friendly.
    """

    # ruff: noqa: N802 - Property names match PATCHPAL_* env var names (uppercase by convention)

    # ============================================================================
    # Model Configuration
    # ============================================================================

    @property
    def MODEL(self) -> str:
        """Default LLM model to use."""
        return os.getenv("PATCHPAL_MODEL", "anthropic/claude-sonnet-4-5")

    @property
    def LLM_TIMEOUT(self) -> int:
        """Timeout for LLM API calls in seconds (default: 300 = 5 minutes)."""
        return int(os.getenv("PATCHPAL_LLM_TIMEOUT", "300"))

    @property
    def SYSTEM_PROMPT(self) -> Optional[str]:
        """Path to custom system prompt file (optional)."""
        return os.getenv("PATCHPAL_SYSTEM_PROMPT")

    @property
    def LITELLM_KWARGS(self) -> Optional[str]:
        """JSON string of additional kwargs to pass to LiteLLM (optional)."""
        return os.getenv("PATCHPAL_LITELLM_KWARGS")

    # ============================================================================
    # Tool Configuration
    # ============================================================================

    @property
    def ENABLE_WEB(self) -> bool:
        """Enable web search and fetch tools (default: true)."""
        return _get_env_bool("PATCHPAL_ENABLE_WEB", "true")

    @property
    def ENABLE_MCP(self) -> bool:
        """Enable Model Context Protocol tools (default: true)."""
        return _get_env_bool("PATCHPAL_ENABLE_MCP", "true")

    @property
    def MINIMAL_TOOLS(self) -> bool:
        """Use minimal tool set for local models (default: false)."""
        return _get_env_bool("PATCHPAL_MINIMAL_TOOLS", "false")

    # ============================================================================
    # File Operations Configuration
    # ============================================================================

    @property
    def MAX_FILE_SIZE(self) -> int:
        """Maximum file size to read in bytes (default: 500KB = 512,000 bytes)."""
        return int(os.getenv("PATCHPAL_MAX_FILE_SIZE", str(500 * 1024)))

    @property
    def MAX_IMAGE_SIZE(self) -> int:
        """Maximum image file size in bytes (default: 10MB)."""
        return int(os.getenv("PATCHPAL_MAX_IMAGE_SIZE", str(10 * 1024 * 1024)))

    @property
    def BLOCK_IMAGES(self) -> bool:
        """Block images from being sent to LLM (default: false).

        When enabled, images are replaced with text placeholders before sending to the model.
        Useful for non-vision models or to reduce costs/privacy concerns.
        """
        return _get_env_bool("PATCHPAL_BLOCK_IMAGES", "false")

    @property
    def READ_ONLY(self) -> bool:
        """Prevent all file modifications (default: false)."""
        return _get_env_bool("PATCHPAL_READ_ONLY", "false")

    @property
    def ALLOW_SENSITIVE(self) -> bool:
        """Allow reading/writing sensitive files like .env (default: false)."""
        return _get_env_bool("PATCHPAL_ALLOW_SENSITIVE", "false")

    @property
    def RESTRICT_TO_REPO(self) -> bool:
        """Restrict file access to repository only (default: false).

        When enabled, prevents reading/writing files outside the repository directory.
        Useful for preventing PII leakage from files in other directories.
        """
        return _get_env_bool("PATCHPAL_RESTRICT_TO_REPO", "false")

    @property
    def ENABLE_BACKUPS(self) -> bool:
        """Create backups before modifying files (default: false)."""
        return _get_env_bool("PATCHPAL_ENABLE_BACKUPS", "false")

    # ============================================================================
    # Shell Command Configuration
    # ============================================================================

    @property
    def SHELL_TIMEOUT(self) -> int:
        """Timeout for shell commands in seconds (default: 30)."""
        return int(os.getenv("PATCHPAL_SHELL_TIMEOUT", "30"))

    @property
    def ALLOW_SUDO(self) -> bool:
        """Allow dangerous operations like sudo (default: false)."""
        return _get_env_bool("PATCHPAL_ALLOW_SUDO", "false")

    # ============================================================================
    # Output Filtering Configuration
    # ============================================================================

    @property
    def FILTER_OUTPUTS(self) -> bool:
        """Filter verbose command outputs to reduce tokens (default: true)."""
        return _get_env_bool("PATCHPAL_FILTER_OUTPUTS", "true")

    @property
    def MAX_OUTPUT_LINES(self) -> int:
        """Maximum lines of shell command output (default: 500)."""
        return int(os.getenv("PATCHPAL_MAX_OUTPUT_LINES", "500"))

    @property
    def MAX_TOOL_OUTPUT_LINES(self) -> int:
        """Maximum lines of tool output before truncation (default: 2000)."""
        return int(os.getenv("PATCHPAL_MAX_TOOL_OUTPUT_LINES", "2000"))

    @property
    def MAX_TOOL_OUTPUT_CHARS(self) -> int:
        """Maximum characters of tool output (default: 100,000)."""
        return int(os.getenv("PATCHPAL_MAX_TOOL_OUTPUT_CHARS", "100000"))

    # ============================================================================
    # Web Tools Configuration
    # ============================================================================

    @property
    def WEB_TIMEOUT(self) -> int:
        """Timeout for web requests in seconds (default: 30)."""
        return int(os.getenv("PATCHPAL_WEB_TIMEOUT", "30"))

    @property
    def MAX_WEB_SIZE(self) -> int:
        """Maximum web content size to download in bytes (default: 5MB)."""
        return int(os.getenv("PATCHPAL_MAX_WEB_SIZE", str(5 * 1024 * 1024)))

    @property
    def VERIFY_SSL(self) -> Optional[str]:
        """SSL verification for web requests (optional, default: verify)."""
        return os.getenv("PATCHPAL_VERIFY_SSL")

    # ============================================================================
    # Permission System Configuration
    # ============================================================================

    @property
    def REQUIRE_PERMISSION(self) -> bool:
        """Require user permission for operations (default: true)."""
        return _get_env_bool("PATCHPAL_REQUIRE_PERMISSION", "true")

    # ============================================================================
    # Audit and Logging Configuration
    # ============================================================================

    @property
    def AUDIT_LOG(self) -> bool:
        """Enable audit logging (default: true)."""
        return _get_env_bool("PATCHPAL_AUDIT_LOG", "true")

    # ============================================================================
    # Resource Limits
    # ============================================================================

    @property
    def MAX_OPERATIONS(self) -> int:
        """Maximum number of operations per session (default: 10,000)."""
        return int(os.getenv("PATCHPAL_MAX_OPERATIONS", "10000"))

    @property
    def MAX_ITERATIONS(self) -> int:
        """Maximum agent loop iterations (default: 100)."""
        return int(os.getenv("PATCHPAL_MAX_ITERATIONS", "100"))

    # ============================================================================
    # Context Window Management
    # ============================================================================

    @property
    def CONTEXT_LIMIT(self) -> Optional[str]:
        """Override context window limit for model (optional)."""
        return os.getenv("PATCHPAL_CONTEXT_LIMIT")

    @property
    def PRUNE_PROTECT(self) -> int:
        """Keep last N tokens of tool outputs when pruning (default: 40,000)."""
        return int(os.getenv("PATCHPAL_PRUNE_PROTECT", "40000"))

    @property
    def PRUNE_MINIMUM(self) -> int:
        """Minimum tokens to prune for it to be worthwhile (default: 20,000)."""
        return int(os.getenv("PATCHPAL_PRUNE_MINIMUM", "20000"))

    @property
    def COMPACT_THRESHOLD(self) -> float:
        """Compact at N% of context capacity (default: 0.75 = 75%)."""
        return float(os.getenv("PATCHPAL_COMPACT_THRESHOLD", "0.75"))

    @property
    def PROACTIVE_PRUNING(self) -> bool:
        """Proactively prune after tool calls when outputs exceed PRUNE_PROTECT (default: true)."""
        return _get_env_bool("PATCHPAL_PROACTIVE_PRUNING", "true")

    @property
    def DISABLE_AUTOCOMPACT(self) -> bool:
        """Disable automatic context compaction (default: false)."""
        return _get_env_bool("PATCHPAL_DISABLE_AUTOCOMPACT", "false")

    # ============================================================================
    # Special Modes
    # ============================================================================

    @property
    def AUTOPILOT_CONFIRMED(self) -> bool:
        """Skip autopilot confirmation prompt (for CI/CD) (default: false)."""
        return os.getenv("PATCHPAL_AUTOPILOT_CONFIRMED") == "true"


# Singleton instance
config = Config()
