"""PatchPal - An open-source Claude Code clone implemented purely in Python."""

__version__ = "0.17.0"

from patchpal.agent import create_agent
from patchpal.cli.autopilot import autopilot_loop
from patchpal.tools import (
    edit_file,
    read_file,
    run_shell,
    web_fetch,
    web_search,
    write_file,
)

__all__ = [
    "read_file",
    "edit_file",
    "write_file",
    "web_search",
    "web_fetch",
    "run_shell",
    "create_agent",
    "autopilot_loop",
]
