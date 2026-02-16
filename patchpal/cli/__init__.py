"""CLI commands for PatchPal."""

from patchpal.cli.autopilot import main as autopilot_main
from patchpal.cli.interactive import main
from patchpal.cli.mcp import main as mcp_main

__all__ = ["main", "autopilot_main", "mcp_main"]
