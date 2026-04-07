"""
Session management for per-chat agent instances.

Each chat (Telegram/Discord/WhatsApp) gets its own agent session with
isolated conversation history and context.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class ChatSession:
    """Represents a single chat session with its own agent."""

    def __init__(self, chat_id: str, platform: str, agent_factory):
        """
        Initialize chat session.

        Args:
            chat_id: Unique chat identifier
            platform: Platform name (telegram, discord, whatsapp)
            agent_factory: Factory function to create agent instance
        """
        self.chat_id = chat_id
        self.platform = platform
        self.agent = agent_factory()
        self.context_messages = []

    def add_context(self, role: str, content: str):
        """Add message to context."""
        self.context_messages.append({"role": role, "content": content})
        # Keep last 20 messages
        if len(self.context_messages) > 20:
            self.context_messages = self.context_messages[-20:]

    def get_context_str(self) -> str:
        """Get conversation context as string."""
        if not self.context_messages:
            return ""

        lines = []
        for msg in self.context_messages:
            role = msg["role"].capitalize()
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def run(self, prompt: str, memory_file: Optional[Path] = None) -> str:
        """
        Run agent with prompt and context.

        Args:
            prompt: User prompt
            memory_file: Optional MEMORY.md file for this chat

        Returns:
            Agent response
        """
        # Build full prompt with context
        full_prompt = ""

        # Add memory if available
        if memory_file and memory_file.exists():
            memory_content = memory_file.read_text()
            full_prompt += f"# Memory\n{memory_content}\n\n"

        # Add conversation context
        context_str = self.get_context_str()
        if context_str:
            full_prompt += f"# Recent Conversation\n{context_str}\n\n"

        # Add current prompt
        full_prompt += f"# Current Message\n{prompt}"

        # Run agent
        result = self.agent.run(full_prompt)

        # Add to context
        self.add_context("user", prompt)
        self.add_context("assistant", result)

        return result


class SessionManager:
    """Manages chat sessions across all platforms."""

    def __init__(self, agent_factory, message_store):
        """
        Initialize session manager.

        Args:
            agent_factory: Factory function to create agent instances
            message_store: MessageStore instance
        """
        self.agent_factory = agent_factory
        self.message_store = message_store
        self.sessions: Dict[str, ChatSession] = {}
        self.memory_dir = Path.home() / ".patchpal" / "chats"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def get_or_create_session(self, chat_id: str, platform: str) -> ChatSession:
        """
        Get existing session or create new one.

        Args:
            chat_id: Chat identifier
            platform: Platform name

        Returns:
            ChatSession instance
        """
        if chat_id not in self.sessions:
            logger.info(f"Creating new session for {chat_id} ({platform})")
            session = ChatSession(chat_id, platform, self.agent_factory)

            # Load conversation context from message store
            messages = self.message_store.get_messages(chat_id, limit=20)
            for msg in messages:
                session.add_context(msg["role"], msg["content"])

            self.sessions[chat_id] = session

        return self.sessions[chat_id]

    def get_memory_file(self, chat_id: str) -> Path:
        """
        Get memory file path for a chat.

        Args:
            chat_id: Chat identifier

        Returns:
            Path to MEMORY.md file
        """
        # Sanitize chat_id for filename
        safe_id = chat_id.replace(":", "_").replace("/", "_")
        return self.memory_dir / f"{safe_id}_MEMORY.md"

    def run_in_session(self, chat_id: str, platform: str, prompt: str) -> str:
        """
        Run prompt in chat session.

        Args:
            chat_id: Chat identifier
            platform: Platform name
            prompt: User prompt

        Returns:
            Agent response
        """
        session = self.get_or_create_session(chat_id, platform)
        memory_file = self.get_memory_file(chat_id)
        return session.run(prompt, memory_file)

    def get_all_sessions(self) -> Dict[str, ChatSession]:
        """Get all active sessions."""
        return self.sessions

    def close_session(self, chat_id: str):
        """Close and remove a session."""
        if chat_id in self.sessions:
            del self.sessions[chat_id]
            logger.info(f"Closed session: {chat_id}")

    def close_all_sessions(self):
        """Close all sessions."""
        self.sessions.clear()
        logger.info("Closed all sessions")
