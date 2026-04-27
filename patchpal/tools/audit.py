"""Enhanced audit logging for compliance with enterprise logging requirements.

This module provides structured JSON-based audit logging with:
- Unique session identifiers
- User identity tracking
- Action approval/rejection logging
- Structured format for easy parsing
"""

import json
import os
import uuid
from datetime import datetime
from typing import Optional

from patchpal.config import config

# Session ID - generated once per agent session
_session_id: Optional[str] = None


def get_session_id() -> str:
    """Get or create session ID for this agent run.

    Returns:
        UUID string identifying this session
    """
    global _session_id
    if _session_id is None:
        _session_id = str(uuid.uuid4())
    return _session_id


def reset_session_id():
    """Reset session ID (for testing or new sessions)."""
    global _session_id
    _session_id = None


def get_user_identity() -> str:
    """Get user identity from environment.

    Returns:
        Username from environment or 'unknown'
    """
    # Try multiple environment variables for cross-platform compatibility
    return (
        os.environ.get("USER")
        or os.environ.get("USERNAME")
        or os.environ.get("LOGNAME")
        or "unknown"
    )


def log_action_blocked(
    tool_name: str,
    description: str,
    reason: str,
    pattern: Optional[str] = None,
    context: Optional[dict] = None,
):
    """Log a blocked/rejected action.

    Args:
        tool_name: Name of the tool (e.g., 'run_shell', 'write_file')
        description: Human-readable description of the action
        reason: Why the action was blocked (e.g., 'user_rejected', 'dangerous_command', 'sensitive_file')
        pattern: Optional pattern that was blocked (e.g., command pattern, file path)
        context: Optional additional context dictionary
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "ACTION_BLOCKED",
        "tool_name": tool_name,
        "description": description,
        "reason": reason,
        "outcome": "rejected",
    }

    if pattern:
        entry["pattern"] = pattern

    if context:
        entry["context"] = context

    # Log as JSON for structured parsing
    audit_logger.info(json.dumps(entry))


def log_action_approved(
    tool_name: str,
    description: str,
    approval_type: str = "user_approved",
    pattern: Optional[str] = None,
    context: Optional[dict] = None,
):
    """Log an approved action.

    Args:
        tool_name: Name of the tool
        description: Human-readable description of the action
        approval_type: Type of approval (e.g., 'user_approved', 'session_granted', 'auto_granted')
        pattern: Optional pattern that was approved
        context: Optional additional context dictionary
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "ACTION_APPROVED",
        "tool_name": tool_name,
        "description": description,
        "approval_type": approval_type,
        "outcome": "approved",
    }

    if pattern:
        entry["pattern"] = pattern

    if context:
        entry["context"] = context

    audit_logger.info(json.dumps(entry))


def log_action_result(
    tool_name: str,
    description: str,
    success: bool,
    error: Optional[str] = None,
    context: Optional[dict] = None,
):
    """Log the result of an action execution.

    Args:
        tool_name: Name of the tool
        description: Human-readable description of the action
        success: Whether the action succeeded
        error: Optional error message if action failed
        context: Optional additional context dictionary
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "ACTION_RESULT",
        "tool_name": tool_name,
        "description": description,
        "outcome": "success" if success else "error",
    }

    if error:
        entry["error"] = error

    if context:
        entry["context"] = context

    audit_logger.info(json.dumps(entry))


def log_session_start(agent_type: str = "function_calling", model: str = "unknown"):
    """Log the start of a new agent session.

    Args:
        agent_type: Type of agent (e.g., 'function_calling', 'react')
        model: Model identifier being used
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "SESSION_START",
        "agent_type": agent_type,
        "model": model,
    }

    audit_logger.info(json.dumps(entry))


def log_session_end(total_operations: int = 0, success: bool = True):
    """Log the end of an agent session.

    Args:
        total_operations: Total number of operations performed
        success: Whether the session completed successfully
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "SESSION_END",
        "total_operations": total_operations,
        "outcome": "success" if success else "error",
    }

    audit_logger.info(json.dumps(entry))
