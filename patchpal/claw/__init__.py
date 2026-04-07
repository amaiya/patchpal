"""
PatchPal Claw - Background automation features.

Inspired by ClaudeClaw/OpenClaw, this module provides lightweight
background automation with cron-style scheduling and notifications.

Features:
- Job scheduling (cron expressions)
- Cache management (deduplication)
- Telegram notifications
- Background daemon

Usage:
    # From command line
    patchpal-daemon

    # From Python
    from patchpal.claw import cache, scheduler

Install optional dependencies:
    pip install patchpal[claw]  # Includes croniter + telegram
"""

from . import cache, scheduler

__all__ = ["cache", "scheduler"]
