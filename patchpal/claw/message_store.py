"""
Message storage for persistent conversation history.

Stores messages from all chat platforms (Telegram, Discord, WhatsApp)
in SQLite for persistent conversation across daemon restarts.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MessageStore:
    """SQLite-based message storage."""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize message store.

        Args:
            db_path: Path to SQLite database (default: ~/.patchpal/messages.db)
        """
        if db_path is None:
            db_path = Path.home() / ".patchpal" / "messages.db"

        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_schema()

    def _create_schema(self):
        """Create database schema."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                name TEXT,
                trigger_pattern TEXT DEFAULT '@patchpal',
                last_message_time TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            );

            CREATE INDEX IF NOT EXISTS idx_chat_timestamp
            ON messages(chat_id, timestamp);

            CREATE TABLE IF NOT EXISTS sessions (
                chat_id TEXT PRIMARY KEY,
                session_data TEXT,
                last_active TEXT,
                FOREIGN KEY (chat_id) REFERENCES chats(chat_id)
            );
        """)
        self.conn.commit()

    def register_chat(
        self,
        chat_id: str,
        platform: str,
        name: Optional[str] = None,
        trigger_pattern: str = "@patchpal",
    ):
        """
        Register a new chat.

        Args:
            chat_id: Unique chat identifier (platform:id format)
            platform: Platform name (telegram, discord, whatsapp)
            name: Human-readable chat name
            trigger_pattern: Trigger word for this chat
        """
        self.conn.execute(
            """
            INSERT OR REPLACE INTO chats (chat_id, platform, name, trigger_pattern, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, platform, name, trigger_pattern, datetime.now().isoformat()),
        )
        self.conn.commit()
        logger.info(f"Registered chat: {chat_id} ({platform})")

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """
        Add a message to the store.

        Args:
            chat_id: Chat identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (JSON)
        """
        import json

        self.conn.execute(
            """
            INSERT INTO messages (chat_id, role, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                role,
                content,
                datetime.now().isoformat(),
                json.dumps(metadata) if metadata else None,
            ),
        )

        # Update last_message_time in chats
        self.conn.execute(
            """
            UPDATE chats SET last_message_time = ? WHERE chat_id = ?
            """,
            (datetime.now().isoformat(), chat_id),
        )

        self.conn.commit()

    def get_messages(
        self, chat_id: str, limit: Optional[int] = None, since: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get messages for a chat.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of messages (most recent)
            since: Get messages after this timestamp

        Returns:
            List of message dicts
        """
        import json

        query = """
            SELECT role, content, timestamp, metadata
            FROM messages
            WHERE chat_id = ?
        """
        params: list = [chat_id]

        if since:
            query += " AND timestamp > ?"
            params.append(since)

        query += " ORDER BY timestamp ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = self.conn.execute(query, params)
        messages = []
        for row in cursor:
            msg = {
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            if row["metadata"]:
                msg["metadata"] = json.loads(row["metadata"])
            messages.append(msg)

        return messages

    def get_new_messages(self, last_timestamp: str) -> List[Dict[str, Any]]:
        """
        Get all new messages across all chats since timestamp.

        Args:
            last_timestamp: Get messages after this timestamp

        Returns:
            List of message dicts with chat_id
        """
        import json

        cursor = self.conn.execute(
            """
            SELECT chat_id, role, content, timestamp, metadata
            FROM messages
            WHERE timestamp > ? AND role = 'user'
            ORDER BY timestamp ASC
            """,
            (last_timestamp,),
        )

        messages = []
        for row in cursor:
            msg = {
                "chat_id": row["chat_id"],
                "role": row["role"],
                "content": row["content"],
                "timestamp": row["timestamp"],
            }
            if row["metadata"]:
                msg["metadata"] = json.loads(row["metadata"])
            messages.append(msg)

        return messages

    def get_chat(self, chat_id: str) -> Optional[Dict[str, Any]]:
        """Get chat metadata."""
        cursor = self.conn.execute(
            """
            SELECT chat_id, platform, name, trigger_pattern, last_message_time, created_at
            FROM chats
            WHERE chat_id = ?
            """,
            (chat_id,),
        )
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None

    def get_all_chats(self) -> List[Dict[str, Any]]:
        """Get all registered chats."""
        cursor = self.conn.execute(
            """
            SELECT chat_id, platform, name, trigger_pattern, last_message_time, created_at
            FROM chats
            ORDER BY last_message_time DESC
            """
        )
        return [dict(row) for row in cursor]

    def save_session_data(self, chat_id: str, session_data: str):
        """Save session data for a chat."""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO sessions (chat_id, session_data, last_active)
            VALUES (?, ?, ?)
            """,
            (chat_id, session_data, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_session_data(self, chat_id: str) -> Optional[str]:
        """Get session data for a chat."""
        cursor = self.conn.execute(
            """
            SELECT session_data FROM sessions WHERE chat_id = ?
            """,
            (chat_id,),
        )
        row = cursor.fetchone()
        if row:
            return row["session_data"]
        return None

    def get_conversation_context(self, chat_id: str, max_messages: int = 20) -> str:
        """
        Get conversation context as formatted string.

        Args:
            chat_id: Chat identifier
            max_messages: Maximum messages to include

        Returns:
            Formatted conversation context
        """
        messages = self.get_messages(chat_id, limit=max_messages)
        if not messages:
            return ""

        context = []
        for msg in messages:
            role = msg["role"].capitalize()
            content = msg["content"]
            context.append(f"{role}: {content}")

        return "\n".join(context)

    def close(self):
        """Close database connection."""
        self.conn.close()
