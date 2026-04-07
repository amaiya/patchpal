"""
Discord bot integration for bidirectional messaging.

Receives messages from Discord and stores them in the message store.
The daemon polls the message store and responds via this bot.
"""

import logging
import os
from typing import Callable

logger = logging.getLogger(__name__)

# Try to import discord, but don't fail if not installed
try:
    import discord

    DISCORD_BOT_AVAILABLE = True
except ImportError:
    DISCORD_BOT_AVAILABLE = False
    discord = None


class DiscordBot(discord.Client if discord else object):
    """Discord bot for receiving messages."""

    def __init__(
        self,
        token: str,
        on_message_callback: Callable[[str, str, str], None],
        trigger_pattern: str = "@patchpal",
    ):
        """
        Initialize Discord bot.

        Args:
            token: Discord bot token
            on_message_callback: Callback(chat_id, message_text, sender_name)
            trigger_pattern: Trigger word to respond to
        """
        if not DISCORD_BOT_AVAILABLE:
            raise ImportError("discord.py not installed. Install with: pip install discord.py")

        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)

        self.token = token
        self.on_message_callback = on_message_callback
        self.trigger_pattern = trigger_pattern.lower()
        self.running = False

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Discord bot logged in as {self.user}")
        self.running = True

    async def on_message(self, message: discord.Message):
        """Handle incoming message."""
        # Don't respond to ourselves
        if message.author == self.user:
            return

        chat_id = f"discord:{message.channel.id}"
        message_text = message.content
        sender_name = message.author.name

        logger.info(f"Discord message from {sender_name} ({chat_id}): {message_text[:50]}...")

        # Store message via callback
        self.on_message_callback(chat_id, message_text, sender_name)

    async def start_bot(self):
        """Start the bot."""
        try:
            await self.start(self.token)
        except Exception as e:
            logger.error(f"Discord bot error: {e}")
            raise

    async def send_message(self, chat_id: str, text: str):
        """Send message to a channel."""
        try:
            # Extract channel ID from chat_id (format: discord:123456)
            channel_id = int(chat_id.split(":")[1])
            channel = self.get_channel(channel_id)

            if not channel:
                logger.error(f"Channel not found: {channel_id}")
                return

            await channel.send(text)
            logger.info(f"Sent Discord message to {chat_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send Discord message to {chat_id}: {e}")

    async def stop_bot(self):
        """Stop the bot."""
        if self.running:
            await self.close()
            self.running = False
            logger.info("Discord bot stopped")

    @staticmethod
    def is_configured() -> bool:
        """Check if Discord bot is configured."""
        return bool(os.getenv("DISCORD_BOT_TOKEN"))

    @staticmethod
    def is_available() -> bool:
        """Check if Discord bot library is available."""
        return DISCORD_BOT_AVAILABLE
