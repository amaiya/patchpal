#!/usr/bin/env python
"""
PatchPal Claw Daemon - General AI Assistant

A background daemon that:
1. Runs scheduled jobs (automation)
2. Receives messages from Telegram/Discord (chat bot)
3. Maintains conversation sessions per chat
4. Proactively monitors via HEARTBEAT

Inspired by ClaudeClaw/NanoClaw architecture.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class GeneralAssistantDaemon:
    """PatchPal Claw - General AI Assistant Daemon."""

    def __init__(
        self,
        agent_factory=None,
        job_check_interval: int = 60,
        message_poll_interval: int = 5,
        heartbeat_interval: int = 900,  # 15 minutes
    ):
        """
        Initialize daemon.

        Args:
            agent_factory: Factory function for creating agent instances
            job_check_interval: Seconds between job checks (default: 60)
            message_poll_interval: Seconds between message polls (default: 5)
            heartbeat_interval: Seconds between heartbeat checks (default: 900 = 15 min)
        """
        self.agent_factory = agent_factory or self._default_agent_factory
        self.job_check_interval = job_check_interval
        self.message_poll_interval = message_poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.running = False
        self.last_processed_timestamp = datetime.now().isoformat()

        # Initialize components
        self.message_store = None
        self.session_manager = None
        self.bot_manager = None
        self.heartbeat_enabled = os.getenv("HEARTBEAT_ENABLED", "false").lower() == "true"

    def _default_agent_factory(self):
        """Default agent factory - creates basic agent."""
        # Import here to avoid circular imports
        from patchpal.agent import Agent

        return Agent()

    def _initialize_components(self):
        """Initialize all components."""
        from patchpal.claw.bot_manager import BotManager
        from patchpal.claw.message_store import MessageStore
        from patchpal.claw.session_manager import SessionManager

        # Message store
        self.message_store = MessageStore()
        logger.info(f"Message store initialized: {self.message_store.db_path}")

        # Session manager
        self.session_manager = SessionManager(self.agent_factory, self.message_store)
        logger.info("Session manager initialized")

        # Bot manager
        self.bot_manager = BotManager(self.message_store, self.session_manager)
        logger.info("Bot manager initialized")

    async def start_async(self):
        """Start the daemon (async version)."""
        self.running = True

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        logger.info("=" * 60)
        logger.info("PatchPal Claw Daemon starting...")
        logger.info("=" * 60)

        # Initialize components
        self._initialize_components()

        # Show configuration
        self._show_configuration()

        # Start bots in background
        asyncio.create_task(self._run_bots())

        # Start main loops
        await asyncio.gather(
            self._job_loop(),
            self._message_loop(),
            self._heartbeat_loop() if self.heartbeat_enabled else self._noop_loop(),
        )

    def _show_configuration(self):
        """Show daemon configuration."""
        from patchpal.claw.scheduler import get_job_stats

        # Job stats
        stats = get_job_stats()
        logger.info(f"Jobs: {stats['total']} total ({stats['enabled']} enabled)")

        # Bot platforms
        platforms = self.bot_manager.get_configured_platforms()
        if platforms:
            logger.info(f"Chat platforms: {', '.join(platforms)}")
        else:
            logger.info("Chat platforms: None configured")

        # Heartbeat
        if self.heartbeat_enabled:
            logger.info(f"Heartbeat: Enabled (every {self.heartbeat_interval // 60} minutes)")
        else:
            logger.info("Heartbeat: Disabled")

        # Intervals
        logger.info(f"Job check interval: {self.job_check_interval}s")
        logger.info(f"Message poll interval: {self.message_poll_interval}s")

        logger.info("=" * 60)
        logger.info("Daemon running. Press Ctrl-C to stop.")
        logger.info("=" * 60)

    async def _run_bots(self):
        """Run chat bots."""
        try:
            await self.bot_manager.start_bots()
        except Exception as e:
            logger.error(f"Error in bot manager: {e}", exc_info=True)

    async def _job_loop(self):
        """Job scheduler loop - checks and runs scheduled jobs."""
        from patchpal.claw.scheduler import get_pending_jobs, load_jobs, run_job

        logger.info("Job scheduler loop started")

        while self.running:
            try:
                # Load jobs
                jobs = load_jobs()

                # Get pending jobs
                pending = get_pending_jobs(jobs)

                if pending:
                    logger.info(f"Found {len(pending)} pending jobs")

                    for job in pending:
                        try:
                            logger.info(f"Executing job: {job.name}")
                            result = run_job(job, self.agent_factory)

                            # Send notifications via bots (if job has notify: true)
                            if job.notify and result.get("success"):
                                await self._send_job_notification(job, result)

                        except Exception as e:
                            logger.error(f"Error executing job {job.name}: {e}", exc_info=True)

                await asyncio.sleep(self.job_check_interval)

            except Exception as e:
                logger.error(f"Error in job loop: {e}", exc_info=True)
                await asyncio.sleep(self.job_check_interval)

    async def _send_job_notification(self, job, result):
        """Send job result as notification to all configured chats."""
        result_text = result.get("result", "")
        elapsed = result.get("elapsed", 0)

        # Format message
        message = f"✅ Job: {job.name}\n"
        message += f"Duration: {elapsed:.1f}s\n\n"
        message += result_text[:1000]  # Truncate if too long

        # Send to all active chats
        chats = self.message_store.get_all_chats()

        if not chats:
            logger.debug("No active chats to send job notification to")
            return

        for chat in chats:
            try:
                await self.bot_manager.send_message(chat["chat_id"], message)
                logger.info(f"Sent job notification to {chat['chat_id']}")
            except Exception as e:
                logger.error(f"Failed to send job notification to {chat['chat_id']}: {e}")

    async def _message_loop(self):
        """Message processing loop - polls for new messages and responds."""
        logger.info("Message processing loop started")

        while self.running:
            try:
                # Get new messages since last check
                new_messages = self.message_store.get_new_messages(self.last_processed_timestamp)

                for msg in new_messages:
                    try:
                        await self._process_message(msg)
                        self.last_processed_timestamp = msg["timestamp"]
                    except Exception as e:
                        logger.error(f"Error processing message: {e}", exc_info=True)

                await asyncio.sleep(self.message_poll_interval)

            except Exception as e:
                logger.error(f"Error in message loop: {e}", exc_info=True)
                await asyncio.sleep(self.message_poll_interval)

    async def _process_message(self, message):
        """Process a single message."""
        chat_id = message["chat_id"]
        content = message["content"]

        # Get chat info
        chat = self.message_store.get_chat(chat_id)
        if not chat:
            logger.warning(f"Chat not found: {chat_id}")
            return

        trigger_pattern = chat.get("trigger_pattern", "@patchpal").lower()

        # Check if message contains trigger
        if trigger_pattern not in content.lower():
            logger.debug(f"Message doesn't contain trigger: {content[:50]}...")
            return

        logger.info(f"Processing message from {chat_id}: {content[:50]}...")

        # Run in session
        platform = chat["platform"]
        response = self.session_manager.run_in_session(chat_id, platform, content)

        # Send response
        await self.bot_manager.send_message(chat_id, response)

        logger.info(f"Sent response to {chat_id}: {response[:50]}...")

    async def _heartbeat_loop(self):
        """Heartbeat loop - periodic proactive checks."""
        logger.info(f"Heartbeat loop started (every {self.heartbeat_interval // 60} minutes)")

        while self.running:
            try:
                await asyncio.sleep(self.heartbeat_interval)
                await self._run_heartbeat()
            except Exception as e:
                logger.error(f"Error in heartbeat loop: {e}", exc_info=True)

    async def _run_heartbeat(self):
        """Run heartbeat check across all active sessions."""
        logger.info("Running heartbeat check...")

        # Load heartbeat prompt template
        heartbeat_template_path = Path(__file__).parent / "HEARTBEAT.md"
        if heartbeat_template_path.exists():
            heartbeat_template = heartbeat_template_path.read_text()
        else:
            # Fallback if file missing
            heartbeat_template = """
Review our recent conversation and check for any pending tasks, reminders,
or follow-ups that need attention.

Current time: {current_time}

Recent conversation:
{conversation_history}

If something needs attention, send a casual message about it.
If nothing needs attention, reply exactly: HEARTBEAT_OK
"""

        # Get all chats
        chats = self.message_store.get_all_chats()

        for chat in chats:
            try:
                chat_id = chat["chat_id"]
                platform = chat["platform"]

                # Get conversation context
                context = self.message_store.get_conversation_context(chat_id, max_messages=10)

                # Build heartbeat prompt from template
                heartbeat_prompt = heartbeat_template.format(
                    current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    conversation_history=context,
                )

                # Run in session
                response = self.session_manager.run_in_session(chat_id, platform, heartbeat_prompt)

                # Send if not HEARTBEAT_OK
                if "HEARTBEAT_OK" not in response.upper():
                    await self.bot_manager.send_message(chat_id, response)
                    logger.info(f"Heartbeat sent to {chat_id}: {response[:50]}...")
                else:
                    logger.debug(f"Heartbeat OK for {chat_id}")

            except Exception as e:
                logger.error(f"Error in heartbeat for {chat_id}: {e}", exc_info=True)

    async def _noop_loop(self):
        """No-op loop when heartbeat is disabled."""
        while self.running:
            await asyncio.sleep(3600)  # Sleep for 1 hour

    def _handle_signal(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Received shutdown signal, stopping daemon...")
        self.running = False

    async def stop_async(self):
        """Stop the daemon."""
        self.running = False

        if self.bot_manager:
            await self.bot_manager.stop_bots()

        if self.session_manager:
            self.session_manager.close_all_sessions()

        if self.message_store:
            self.message_store.close()

        logger.info("Daemon stopped")

    # Synchronous wrappers for backwards compatibility
    def start(self):
        """Start the daemon (sync wrapper)."""
        asyncio.run(self.start_async())

    def stop(self):
        """Stop the daemon (sync wrapper)."""
        asyncio.run(self.stop_async())


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PatchPal Claw - General AI Assistant Daemon",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
PatchPal Claw is a general AI assistant that:
- Runs scheduled automation jobs
- Chats with you via Telegram/Discord
- Remembers conversations and context
- Proactively checks in (HEARTBEAT)

Configuration (environment variables):

  Chat Platforms:
    TELEGRAM_BOT_TOKEN - Telegram bot token
    DISCORD_BOT_TOKEN - Discord bot token

  Heartbeat:
    HEARTBEAT_ENABLED - Enable heartbeat (true/false)

  Trigger:
    TRIGGER_PATTERN - Word to trigger responses (default: @patchpal)

Setup Telegram:
  1. Talk to @BotFather on Telegram
  2. Create bot with /newbot
  3. Copy token: export TELEGRAM_BOT_TOKEN="123456:ABC-DEF..."
  4. Start daemon: patchpal-daemon
  5. Send message: "@patchpal hello"

Setup Discord:
  1. Create bot at https://discord.com/developers/applications
  2. Enable "Message Content Intent" in Bot settings
  3. Copy token: export DISCORD_BOT_TOKEN="MTA5..."
  4. Invite bot to server
  5. Send message: "@patchpal hello"

Jobs:
  Define in ~/.patchpal/jobs/*.yaml
  See examples/automation/jobs/ for examples

Examples:
  # Start daemon
  patchpal-daemon

  # Enable heartbeat
  HEARTBEAT_ENABLED=true patchpal-daemon

  # Custom intervals
  patchpal-daemon --job-interval 30 --message-interval 3

  # Show status
  patchpal-daemon --status
        """,
    )

    parser.add_argument(
        "--job-interval",
        type=int,
        default=60,
        help="Job check interval in seconds (default: 60)",
    )

    parser.add_argument(
        "--message-interval",
        type=int,
        default=5,
        help="Message poll interval in seconds (default: 5)",
    )

    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=900,
        help="Heartbeat interval in seconds (default: 900 = 15 min)",
    )

    parser.add_argument("--status", action="store_true", help="Show status and exit")

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    # Show status
    if args.status:
        from patchpal.claw.message_store import MessageStore
        from patchpal.claw.scheduler import get_job_stats

        stats = get_job_stats()
        print("PatchPal Claw Status")
        print("=" * 60)
        print(f"Jobs: {stats['total']} total ({stats['enabled']} enabled)")
        print(f"Jobs directory: {stats['jobs_dir']}")

        # Check platforms
        platforms = []
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            platforms.append("Telegram ✓")
        if os.getenv("DISCORD_BOT_TOKEN"):
            platforms.append("Discord ✓")

        if platforms:
            print(f"Chat platforms: {', '.join(platforms)}")
        else:
            print("Chat platforms: None configured")

        # Heartbeat
        heartbeat = os.getenv("HEARTBEAT_ENABLED", "false").lower() == "true"
        print(f"Heartbeat: {'Enabled ✓' if heartbeat else 'Disabled'}")

        # Chats
        try:
            store = MessageStore()
            chats = store.get_all_chats()
            print(f"Active chats: {len(chats)}")
            for chat in chats[:5]:  # Show first 5
                print(f"  - {chat['platform']}: {chat['name'] or chat['chat_id']}")
            if len(chats) > 5:
                print(f"  ... and {len(chats) - 5} more")
            store.close()
        except Exception as e:
            print(f"Active chats: Error ({e})")

        print("=" * 60)
        return 0

    # Start daemon
    daemon = GeneralAssistantDaemon(
        job_check_interval=args.job_interval,
        message_poll_interval=args.message_interval,
        heartbeat_interval=args.heartbeat_interval,
    )

    try:
        daemon.start()
    except KeyboardInterrupt:
        logger.info("Daemon stopped by user")
    except Exception as e:
        logger.error(f"Daemon error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
