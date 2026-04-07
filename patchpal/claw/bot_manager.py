"""
Bot manager - orchestrates all chat platforms (Telegram, Discord).

Receives messages from bots, stores them, and coordinates responses.
"""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


class BotManager:
    """Manages all chat bots and coordinates messaging."""

    def __init__(self, message_store, session_manager):
        """
        Initialize bot manager.

        Args:
            message_store: MessageStore instance
            session_manager: SessionManager instance
        """
        self.message_store = message_store
        self.session_manager = session_manager
        self.telegram_bot = None
        self.discord_bot = None
        self.running = False

    def _on_telegram_message(self, chat_id: str, text: str, sender_name: str):
        """Handle Telegram message."""
        full_chat_id = f"telegram:{chat_id}"

        # Register chat if new
        chat = self.message_store.get_chat(full_chat_id)
        if not chat:
            self.message_store.register_chat(full_chat_id, "telegram", sender_name)

        # Store message
        self.message_store.add_message(full_chat_id, "user", text)
        logger.info(f"Stored Telegram message from {sender_name}")

    def _on_discord_message(self, chat_id: str, text: str, sender_name: str):
        """Handle Discord message."""
        # chat_id already includes "discord:" prefix

        # Register chat if new
        chat = self.message_store.get_chat(chat_id)
        if not chat:
            self.message_store.register_chat(chat_id, "discord", sender_name)

        # Store message
        self.message_store.add_message(chat_id, "user", text)
        logger.info(f"Stored Discord message from {sender_name}")

    async def start_bots(self):
        """Start all configured bots."""
        if self.running:
            return

        tasks = []

        # Start Telegram bot if configured
        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        if telegram_token:
            try:
                from patchpal.claw.telegram_bot import TelegramBot

                self.telegram_bot = TelegramBot(
                    token=telegram_token,
                    on_message=self._on_telegram_message,
                )
                await self.telegram_bot.start()
                logger.info("Telegram bot started")
            except Exception as e:
                logger.error(f"Failed to start Telegram bot: {e}")

        # Start Discord bot if configured
        discord_token = os.getenv("DISCORD_BOT_TOKEN")
        if discord_token:
            try:
                from patchpal.claw.discord_bot import DiscordBot

                self.discord_bot = DiscordBot(
                    token=discord_token,
                    on_message_callback=self._on_discord_message,
                )
                # Discord bot runs in background
                tasks.append(asyncio.create_task(self.discord_bot.start_bot()))
                logger.info("Discord bot starting...")
            except Exception as e:
                logger.error(f"Failed to start Discord bot: {e}")

        self.running = True

        # Keep bots running
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def stop_bots(self):
        """Stop all bots."""
        if not self.running:
            return

        if self.telegram_bot:
            await self.telegram_bot.stop()
            logger.info("Telegram bot stopped")

        if self.discord_bot:
            await self.discord_bot.stop_bot()
            logger.info("Discord bot stopped")

        self.running = False

    async def send_message(self, chat_id: str, text: str):
        """
        Send message to a chat.

        Args:
            chat_id: Full chat ID with platform prefix (e.g., "telegram:123")
            text: Message text
        """
        platform, chat_id_num = chat_id.split(":", 1)

        if platform == "telegram" and self.telegram_bot:
            await self.telegram_bot.send_message(chat_id_num, text)
            # Store our response
            self.message_store.add_message(chat_id, "assistant", text)

        elif platform == "discord" and self.discord_bot:
            await self.discord_bot.send_message(chat_id, text)
            # Store our response
            self.message_store.add_message(chat_id, "assistant", text)

        else:
            logger.error(f"Cannot send message to {chat_id}: bot not configured")

    def get_configured_platforms(self) -> list:
        """Get list of configured platforms."""
        platforms = []
        if os.getenv("TELEGRAM_BOT_TOKEN"):
            platforms.append("Telegram")
        if os.getenv("DISCORD_BOT_TOKEN"):
            platforms.append("Discord")
        return platforms
