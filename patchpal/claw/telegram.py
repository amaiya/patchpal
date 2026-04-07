"""
Telegram notification support for PatchPal.

Simple send-only integration for job notifications.
Configure via TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.

This is an optional feature - requires python-telegram-bot package.
Install with: pip install python-telegram-bot
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import telegram, but don't fail if not installed
try:
    from telegram import Bot
    from telegram.error import TelegramError

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False
    Bot = None
    TelegramError = Exception


def is_configured() -> bool:
    """
    Check if Telegram is configured.

    Returns:
        True if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set

    Example:
        >>> from patchpal.telegram import is_configured
        >>> if is_configured():
        ...     print("Telegram is ready!")
    """
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def is_available() -> bool:
    """
    Check if Telegram library is installed.

    Returns:
        True if python-telegram-bot is installed
    """
    return TELEGRAM_AVAILABLE


def send(text: str, parse_mode: str = "Markdown", disable_notification: bool = False) -> bool:
    """
    Send a message via Telegram.

    Args:
        text: Message text (supports Markdown)
        parse_mode: 'Markdown', 'HTML', or None
        disable_notification: If True, sends silently

    Returns:
        True if message was sent successfully

    Environment Variables:
        TELEGRAM_BOT_TOKEN: Bot token from @BotFather
        TELEGRAM_CHAT_ID: Chat ID to send to

    Example:
        >>> from patchpal.telegram import send
        >>> send("Job completed! Found 3 new posts.")
        >>> send("**Alert:** Job failed!", parse_mode='Markdown')

    Setup:
        1. Talk to @BotFather on Telegram to create a bot
        2. Copy the bot token
        3. Send a message to your bot
        4. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
        5. Copy your chat_id from the response
        6. Set environment variables:
           export TELEGRAM_BOT_TOKEN="your-token"
           export TELEGRAM_CHAT_ID="your-chat-id"
    """
    if not TELEGRAM_AVAILABLE:
        logger.warning(
            "python-telegram-bot not installed. Install with: pip install python-telegram-bot"
        )
        return False

    if not is_configured():
        logger.warning("Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return False

    try:
        bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
        chat_id = os.getenv("TELEGRAM_CHAT_ID")

        bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_notification=disable_notification,
        )

        logger.info(f"Telegram message sent: {text[:50]}...")
        return True

    except TelegramError as e:
        logger.error(f"Failed to send Telegram message: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending Telegram message: {e}")
        return False


def send_job_result(
    job_name: str, result: str, success: bool = True, elapsed: Optional[float] = None
) -> bool:
    """
    Send a formatted job result notification.

    Args:
        job_name: Name of the job
        result: Result text
        success: Whether job succeeded
        elapsed: Execution time in seconds

    Returns:
        True if message was sent successfully

    Example:
        >>> from patchpal.telegram import send_job_result
        >>> send_job_result('reddit-listening', 'Found 3 new posts', True, 12.5)
    """
    if success:
        emoji = "✅"
        status = "Completed"
    else:
        emoji = "❌"
        status = "Failed"

    message = f"{emoji} **{job_name}** {status}"

    if elapsed:
        message += f" ({elapsed:.1f}s)"

    message += f"\n\n{result[:800]}"  # Limit to ~800 chars

    if len(result) > 800:
        message += "\n\n_(truncated)_"

    return send(message)


def send_summary(title: str, items: list, prefix: str = "•") -> bool:
    """
    Send a bulleted summary.

    Args:
        title: Summary title
        items: List of items to include
        prefix: Bullet point prefix

    Returns:
        True if message was sent successfully

    Example:
        >>> from patchpal.telegram import send_summary
        >>> send_summary(
        ...     "New LinkedIn Connections",
        ...     ["John Doe - AI Startup Founder", "Jane Smith - ML Engineer"],
        ...     prefix="🎯"
        ... )
    """
    message = f"**{title}**\n\n"

    for item in items[:10]:  # Limit to 10 items
        message += f"{prefix} {item}\n"

    if len(items) > 10:
        message += f"\n_...and {len(items) - 10} more_"

    return send(message)


def get_setup_instructions() -> str:
    """
    Get Telegram setup instructions.

    Returns:
        Setup instructions as a string
    """
    return """
Telegram Setup Instructions:

1. Create a bot:
   - Open Telegram and talk to @BotFather
   - Send: /newbot
   - Follow the prompts to name your bot
   - Copy the bot token (looks like: 123456:ABC-DEF...)

2. Get your chat ID:
   - Send a message to your new bot
   - Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
   - Copy the "chat":{"id":...} value

3. Set environment variables:
   export TELEGRAM_BOT_TOKEN="your-bot-token"
   export TELEGRAM_CHAT_ID="your-chat-id"

4. Test it:
   python -c "from patchpal.telegram import send; send('Hello from PatchPal!')"

Optional: Add to your ~/.bashrc or ~/.zshrc to persist the variables.
"""
