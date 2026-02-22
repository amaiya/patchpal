"""Shell command execution tools."""

import subprocess
from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    DANGEROUS_PATTERNS,
    DANGEROUS_TOKENS,
    SHELL_TIMEOUT,
    OutputFilter,
    _get_permission_manager,
    _operation_limiter,
    audit_logger,
)


def _extract_shell_command_info(cmd: str) -> tuple[Optional[str], Optional[str]]:
    """Extract the meaningful command pattern and working directory from a shell command.

    Handles compound commands (&&, ||, ;, |) by identifying the primary
    command being executed and any cd commands that change the working directory.
    Also detects command execution wrappers (find -exec, xargs, sh -c) and extracts
    the actual command being executed.

    Args:
        cmd: The shell command string

    Returns:
        Tuple of (command_pattern, working_directory)
        - command_pattern: The primary command name (e.g., 'python')
        - working_directory: The directory if cd is used, None otherwise

    Examples:
        >>> _extract_shell_command_info("pytest tests/")
        ('pytest', None)
        >>> _extract_shell_command_info("cd /tmp && python script.py")
        ('python', '/tmp')
        >>> _extract_shell_command_info("cd src && ls -la | grep test")
        ('ls', 'src')
        >>> _extract_shell_command_info("find . -exec sed -i 's/a/b/g' {} +")
        ('sed', None)
        >>> _extract_shell_command_info("xargs rm -rf")
        ('rm', None)
    """
    if not cmd or not cmd.strip():
        return None, None

    # First, check for command execution wrappers that delegate to other commands
    # These are security-sensitive because they can bypass the harmless command list
    cmd_lower = cmd.strip().lower()

    # find with -exec or -execdir: extract the command after -exec/-execdir
    if cmd_lower.startswith("find "):
        # Look for -exec or -execdir
        for exec_flag in ["-exec", "-execdir"]:
            if exec_flag in cmd_lower:
                # Find the position of -exec/-execdir
                parts = cmd.split()
                try:
                    exec_idx = next(i for i, p in enumerate(parts) if p.lower() == exec_flag)
                    if exec_idx + 1 < len(parts):
                        # Extract the command and possibly the first flag (e.g., 'sed -n')
                        executed_cmd = parts[exec_idx + 1]
                        # Strip common path prefixes and get just the command name
                        if "/" in executed_cmd:
                            executed_cmd = executed_cmd.split("/")[-1]

                        # Check if there's a flag right after the command (e.g., sed -n)
                        # This allows matching multi-word patterns like 'sed -n' in harmless list
                        if exec_idx + 2 < len(parts) and parts[exec_idx + 2].startswith("-"):
                            # Include the flag for patterns like 'sed -n'
                            executed_cmd = f"{executed_cmd} {parts[exec_idx + 2]}"

                        return executed_cmd, None
                except StopIteration:
                    pass

    # xargs: extract the command being executed
    if cmd_lower.startswith("xargs "):
        # xargs runs a command on each line of input
        # The command comes after xargs and its options
        parts = cmd.split()
        # Skip 'xargs' and any options (start with -)
        for i in range(1, len(parts)):
            if not parts[i].startswith("-"):
                executed_cmd = parts[i]
                if "/" in executed_cmd:
                    executed_cmd = executed_cmd.split("/")[-1]

                # Check if there's a flag right after the command (e.g., sed -n)
                if i + 1 < len(parts) and parts[i + 1].startswith("-"):
                    executed_cmd = f"{executed_cmd} {parts[i + 1]}"

                return executed_cmd, None
        # If no command specified, xargs defaults to 'echo' (safe)
        return "echo", None

    # sh -c, bash -c, etc.: extract the command string
    for shell_cmd in ["sh -c", "bash -c", "zsh -c", "ksh -c", "dash -c"]:
        if shell_cmd in cmd_lower:
            # Find what comes after the -c flag
            idx = cmd_lower.index(shell_cmd) + len(shell_cmd)
            remainder = cmd[idx:].strip()
            # The command is usually in quotes, extract first token and possibly flag
            if remainder:
                # Remove leading quotes
                remainder = remainder.lstrip("\"'")
                tokens = remainder.split()
                if tokens:
                    first_token = tokens[0]
                    # Check if there's a flag (e.g., sed -n)
                    if len(tokens) > 1 and tokens[1].startswith("-"):
                        first_token = f"{first_token} {tokens[1]}"
                    return first_token, None

    # eval: extract the command being evaluated
    if cmd_lower.startswith("eval "):
        remainder = cmd[5:].strip().lstrip("\"'")
        tokens = remainder.split()
        if tokens:
            first_token = tokens[0]
            # Check if there's a flag (e.g., sed -n)
            if len(tokens) > 1 and tokens[1].startswith("-"):
                first_token = f"{first_token} {tokens[1]}"
            return first_token, None

    # Shell operators that indicate compound commands
    # Split by && and || first (they group tighter than ;)
    compound_operators = ["&&", "||", ";"]

    # Split by compound operators to find all sub-commands
    commands = [cmd]
    for op in compound_operators:
        new_commands = []
        for c in commands:
            # Split but keep track of which parts are commands
            parts = c.split(op)
            new_commands.extend(parts)
        commands = new_commands

    # Now also handle pipes within each command
    # Pipes are different - we want the first command in a pipe chain
    pipe_split_commands = []
    for c in commands:
        pipe_parts = c.split("|")
        # For pipes, we only care about the first command (before the pipe)
        pipe_split_commands.append(pipe_parts[0])

    commands = pipe_split_commands

    # Commands that change directory or set context (not the actual operation)
    context_commands = {"cd", "pushd", "popd"}
    setup_commands = {"export", "set", "unset", "source", "."}

    # Track if we see a cd command and what directory it goes to
    working_dir = None
    primary_command = None

    for command_part in commands:
        command_part = command_part.strip()
        if not command_part:
            continue

        tokens = command_part.split()
        if not tokens:
            continue

        first_token = tokens[0]

        # If it's a cd command, extract the target directory
        if first_token in context_commands:
            if first_token == "cd" and len(tokens) > 1:
                working_dir = tokens[1]
            continue

        # Skip setup commands
        if first_token in setup_commands:
            continue

        # This is the primary command
        if not primary_command:
            primary_command = first_token
            # If we already found the primary command, we're done
            # (don't need to look at commands after the main one)
            if working_dir is not None or first_token not in context_commands:
                break

    # If we didn't find a primary command (e.g., only "cd /tmp"), use first token
    if not primary_command:
        first_command = commands[0].strip() if commands else ""
        first_token = first_command.split()[0] if first_command.split() else None
        primary_command = first_token

    return primary_command, working_dir


def run_shell(cmd: str) -> str:
    """
    Run a safe shell command in the repository.

    Args:
        cmd: The shell command to execute

    Returns:
        Combined stdout and stderr output

    Raises:
        ValueError: If command contains forbidden operations
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   {cmd}"
    # Extract meaningful command pattern and working directory, handling compound commands
    command_name, working_dir = _extract_shell_command_info(cmd)

    # Create composite pattern: "command@directory" for cd commands, just "command" otherwise
    # Using @ separator for cross-platform compatibility (: would conflict with Windows paths like C:\temp)
    if working_dir and command_name:
        pattern = f"{command_name}@{working_dir}"
    else:
        pattern = command_name

    # Pass working_dir separately for display purposes
    if not permission_manager.request_permission(
        "run_shell", description, pattern=pattern, context=working_dir, full_command=cmd
    ):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"run_shell({cmd[:50]}...)")

    # Check for dangerous tokens (privilege escalation commands)
    # Token-based matching: splits command and checks each token
    if any(tok in DANGEROUS_TOKENS for tok in cmd.split()):
        raise ValueError(
            f"Blocked dangerous command: {cmd}\nForbidden operations: {', '.join(DANGEROUS_TOKENS)}"
        )

    # Check for dangerous patterns (destructive operations)
    # Substring matching: checks if pattern appears anywhere in command
    for pattern in DANGEROUS_PATTERNS:
        if pattern in cmd:
            raise ValueError(
                f"Blocked dangerous pattern in command: {pattern}\nFull command: {cmd}"
            )

    audit_logger.info(f"SHELL: {cmd}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        cwd=common.REPO_ROOT,
        timeout=SHELL_TIMEOUT,
    )

    # Decode output with error handling for problematic characters
    # Use utf-8 on all platforms with 'replace' to handle encoding issues
    stdout = result.stdout.decode("utf-8", errors="replace") if result.stdout else ""
    stderr = result.stderr.decode("utf-8", errors="replace") if result.stderr else ""

    output = stdout + stderr

    # Apply output filtering to reduce token usage
    if OutputFilter.should_filter(cmd):
        filtered_output = OutputFilter.filter_output(cmd, output)
        # Log if we filtered significantly
        original_lines = len(output.split("\n"))
        filtered_lines = len(filtered_output.split("\n"))
        if filtered_lines < original_lines * 0.5:
            audit_logger.info(
                f"SHELL_FILTER: Reduced output from {original_lines} to {filtered_lines} lines "
                f"(~{int((1 - filtered_lines / original_lines) * 100)}% reduction)"
            )
        return filtered_output

    return output
