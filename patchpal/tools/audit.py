"""Enhanced audit logging for compliance with enterprise logging requirements.

This module provides structured JSON-based audit logging with:
- Unique session identifiers
- User identity tracking
- Action approval/rejection logging
- Structured format for easy parsing
- Tamper-evidence via cryptographic hash-chaining (SHA-256)

Each log entry contains:
- A hash of its own contents
- The hash of the previous entry (creating an immutable chain)

This makes logs tamper-evident: modifying any entry breaks the chain.
"""

import hashlib
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from patchpal.config import config

# Session ID - generated once per agent session
_session_id: Optional[str] = None

# Previous entry hash for chain verification
_prev_hash: Optional[str] = None


def _compute_hash(entry: dict) -> str:
    """Compute SHA-256 hash of a log entry.

    Args:
        entry: Log entry dictionary (without hash field)

    Returns:
        Hex-encoded SHA-256 hash
    """
    # Create canonical JSON (sorted keys, no whitespace)
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))

    # Compute SHA-256 hash
    hash_obj = hashlib.sha256(canonical.encode("utf-8"))

    return hash_obj.hexdigest()


def _log_entry(entry: dict):
    """Log an entry with hash-chaining.

    This centralizes the hash-chaining logic:
    - Adds prev_hash from previous entry
    - Computes hash of this entry
    - Updates prev_hash for next entry
    - Logs as JSON

    Args:
        entry: Log entry dictionary (without prev_hash/hash fields)
    """
    if not config.AUDIT_LOG:
        return

    from patchpal.tools.common import audit_logger

    # Add previous hash for chain
    global _prev_hash
    if _prev_hash is not None:
        entry["prev_hash"] = _prev_hash

    # Compute hash of this entry
    entry_hash = _compute_hash(entry)
    entry["hash"] = entry_hash

    # Update prev_hash for next entry
    _prev_hash = entry_hash

    # Log as JSON
    audit_logger.info(json.dumps(entry))


def verify_hash_chain(entries: list[dict]) -> tuple[bool, Optional[str]]:
    """Verify the hash chain of log entries.

    Args:
        entries: List of log entry dictionaries (must include 'hash' and 'prev_hash' fields)

    Returns:
        Tuple of (is_valid, error_message)
        - (True, None) if chain is valid
        - (False, error_message) if chain is broken
    """
    if not entries:
        return True, None

    prev_hash = None

    for i, entry in enumerate(entries):
        # Check if entry has required hash field
        if "hash" not in entry:
            return False, f"Entry {i} missing 'hash' field"

        # Extract hash and prev_hash
        stored_hash = entry.pop("hash")
        stored_prev_hash = entry.get("prev_hash")

        # First entry should have no prev_hash (SESSION_START)
        if i == 0:
            if stored_prev_hash is not None:
                entry["hash"] = stored_hash  # Restore
                return False, "Entry 0 (SESSION_START) should not have 'prev_hash'"
        else:
            # Subsequent entries must have prev_hash matching previous entry
            if stored_prev_hash != prev_hash:
                entry["hash"] = stored_hash  # Restore
                return (
                    False,
                    f"Entry {i}: prev_hash mismatch (expected {prev_hash[:8]}..., got {stored_prev_hash[:8] if stored_prev_hash else None}...)",
                )

        # Compute expected hash
        expected_hash = _compute_hash(entry)

        # Restore hash to entry
        entry["hash"] = stored_hash

        # Verify hash matches
        if stored_hash != expected_hash:
            return (
                False,
                f"Entry {i}: hash mismatch (expected {expected_hash[:8]}..., got {stored_hash[:8]}...)",
            )

        # Update prev_hash for next iteration
        prev_hash = stored_hash

    return True, None


def reset_prev_hash():
    """Reset previous hash (for testing or new sessions)."""
    global _prev_hash
    _prev_hash = None


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

    _log_entry(entry)


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

    _log_entry(entry)


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

    _log_entry(entry)


def log_session_start(agent_type: str = "function_calling", model: str = "unknown"):
    """Log the start of a new agent session.

    Args:
        agent_type: Type of agent (e.g., 'function_calling', 'react')
        model: Model identifier being used
    """
    # Reset chain for new session
    global _prev_hash
    _prev_hash = None

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "SESSION_START",
        "agent_type": agent_type,
        "model": model,
    }

    _log_entry(entry)


def log_session_end(total_operations: int = 0, success: bool = True):
    """Log the end of an agent session.

    Args:
        total_operations: Total number of operations performed
        success: Whether the session completed successfully
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "SESSION_END",
        "total_operations": total_operations,
        "outcome": "success" if success else "error",
    }

    _log_entry(entry)


def log_user_prompt(prompt: str):
    """Log a user prompt/message.

    Args:
        prompt: The user's prompt/request
    """
    # Truncate very long prompts for logging
    max_length = 1000
    if len(prompt) > max_length:
        prompt = prompt[:max_length] + "... (truncated)"

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "USER_PROMPT",
        "prompt": prompt,
    }

    _log_entry(entry)


def log_agent_response(response: str, success: bool = True):
    """Log an agent response.

    Args:
        response: The agent's response
        success: Whether the response was successful
    """
    # Truncate very long responses for logging
    max_length = 1000
    if len(response) > max_length:
        response = response[:max_length] + "... (truncated)"

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "AGENT_RESPONSE",
        "response": response,
        "outcome": "success" if success else "error",
    }

    _log_entry(entry)


def log_tool_execution(tool_name: str, parameters: dict = None, operation_num: int = None):
    """Log a tool execution.

    Args:
        tool_name: Name of the tool (e.g., 'run_shell', 'read_file')
        parameters: Optional dict of parameters passed to the tool
        operation_num: Optional operation number
    """
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "session_id": get_session_id(),
        "user": get_user_identity(),
        "event_type": "TOOL_EXECUTION",
        "tool_name": tool_name,
    }

    if parameters:
        # Truncate large parameter values
        truncated_params = {}
        for key, value in parameters.items():
            if isinstance(value, str) and len(value) > 200:
                truncated_params[key] = value[:200] + "... (truncated)"
            else:
                truncated_params[key] = value
        entry["parameters"] = truncated_params

    if operation_num is not None:
        entry["operation_num"] = operation_num

    _log_entry(entry)
