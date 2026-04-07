"""
PatchPal Claw - General AI Assistant

A general AI assistant with:
- Scheduled automation jobs (cron-based)
- Bidirectional chat (Telegram/Discord)
- Persistent conversation sessions
- Proactive monitoring (HEARTBEAT)
- Message storage and context

Inspired by ClaudeClaw/NanoClaw architecture.

Usage:
    # From command line
    patchpal-daemon

    # Configure platforms
    export TELEGRAM_BOT_TOKEN="..."
    export DISCORD_BOT_TOKEN="..."
    export HEARTBEAT_ENABLED="true"

Install dependencies:
    pip install patchpal[claw]  # Includes croniter + telegram + discord bots
"""

from . import cache, scheduler

__all__ = ["cache", "scheduler"]
