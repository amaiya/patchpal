"""PatchPal - An open-source Claude Code clone implemented purely in Python."""

__version__ = "0.15.0"

from patchpal.agent import create_agent
from patchpal.cli.autopilot import autopilot_loop
from patchpal.tools import (
    apply_patch,
    edit_file,
    get_file_info,
    grep,
    read_file,
    run_shell,
    web_fetch,
    web_search,
)

__all__ = [
    "read_file",
    "get_file_info",
    "edit_file",
    "apply_patch",
    "grep",
    "web_search",
    "web_fetch",
    "run_shell",
    "create_agent",
    "autopilot_loop",
]
