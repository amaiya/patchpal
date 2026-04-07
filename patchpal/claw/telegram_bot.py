"""
Telegram bot integration for bidirectional messaging.

Receives messages from Telegram and stores them in the message store.
The daemon polls the message store and responds via this bot.
"""

import logging
import os
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Try to import telegram, but don't fail if not installed
try:
    from telegram import Update
    from telegram.ext import Application, ContextTypes, MessageHandler, filters

    TELEGRAM_BOT_AVAILABLE = True
except ImportError:
    TELEGRAM_BOT_AVAILABLE = False
    Application = None
    MessageHandler = None
    filters = None
    Update = None
    ContextTypes = None


class TelegramBot:
    """Telegram bot for receiving messages."""

    def __init__(
        self,
        token: str,
        on_message: Callable[[str, str, str], None],
        trigger_pattern: str = "@patchpal",
    ):
        """
        Initialize Telegram bot.

        Args:
            token: Telegram bot token
            on_message: Callback(chat_id, message_text, sender_name)
            trigger_pattern: Trigger word to respond to
        """
        if not TELEGRAM_BOT_AVAILABLE:
            raise ImportError(
                "python-telegram-bot not installed. Install with: pip install patchpal[claw]"
            )

        self.token = token
        self.on_message = on_message
        self.trigger_pattern = trigger_pattern.lower()
        self.app: Optional[Application] = None
        self.running = False

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming message."""
        if not update.message or not update.message.text:
            return

        chat_id = str(update.effective_chat.id)
        message_text = update.message.text
        sender_name = update.effective_user.first_name if update.effective_user else "Unknown"

        logger.info(f"Telegram message from {sender_name} ({chat_id}): {message_text[:50]}...")

        # Store message via callback
        self.on_message(chat_id, message_text, sender_name)

    async def start(self):
        """Start the bot."""
        if self.running:
            return

        self.app = Application.builder().token(self.token).build()

        # Add message handler
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

        logger.info("Starting Telegram bot...")
        await self.app.initialize()
        await self.app.start()
        await self.app.updater.start_polling(drop_pending_updates=True)
        self.running = True
        logger.info("Telegram bot started")

    async def stop(self):
        """Stop the bot."""
        if not self.running or not self.app:
            return

        logger.info("Stopping Telegram bot...")
        await self.app.updater.stop()
        await self.app.stop()
        await self.app.shutdown()
        self.running = False
        logger.info("Telegram bot stopped")

    async def send_message(self, chat_id: str, text: str):
        """Send message to a chat."""
        if not self.app:
            logger.error("Bot not started, cannot send message")
            return

        try:
            await self.app.bot.send_message(chat_id=int(chat_id), text=text)
            logger.info(f"Sent Telegram message to {chat_id}: {text[:50]}...")
        except Exception as e:
            logger.error(f"Failed to send Telegram message to {chat_id}: {e}")

    def is_configured() -> bool:
        """Check if Telegram bot is configured."""
        return bool(os.getenv("TELEGRAM_BOT_TOKEN"))

    def is_available() -> bool:
        """Check if Telegram bot library is available."""
        return TELEGRAM_BOT_AVAILABLE
