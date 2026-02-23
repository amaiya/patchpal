"""File editing tools (apply_patch, edit_file, edit_file_hashline)."""

import difflib
import os
from pathlib import Path
from typing import List, Optional, Union

from patchpal.tools import common
from patchpal.tools.common import (
    MAX_FILE_SIZE,
    READ_ONLY_MODE,
    _backup_file,
    _check_git_status,
    _check_path,
    _format_colored_diff,
    _get_permission_manager,
    _get_permission_pattern_for_path,
    _is_critical_file,
    _is_inside_repo,
    _operation_limiter,
    audit_logger,
)
from patchpal.tools.hashline import (
    AppendEdit,
    EditResult,
    HashlineMismatchError,
    InsertEdit,
    PrependEdit,
    ReplaceEdit,
    SetEdit,
    apply_hashline_edits,
    parse_tag,
)


def _get_outside_repo_warning(path: Path) -> str:
    """Get warning message for writing outside repository.

    Returns empty string for PatchPal's managed files (MEMORY.md, etc.)

    Args:
        path: Resolved Path object to check

    Returns:
        Warning message or empty string
    """
    if not _is_inside_repo(path):
        # Whitelist PatchPal's managed files (MEMORY.md, etc.)
        from patchpal.tools.common import MEMORY_FILE

        if path.resolve() != MEMORY_FILE.resolve():
            return "\n   ⚠️  WARNING: Writing file outside repository\n"
    return ""


# Check if hashline mode is enabled via environment variable
HASHLINE_MODE = os.getenv("PATCHPAL_HASHLINE", "false").lower() in ("true", "1", "yes")


# ============================================================================
# Edit File - Multi-Strategy String Matching
# ============================================================================
# Based on approaches from gemini-cli and OpenCode: try multiple matching
# strategies to handle # whitespace/indentation issues without requiring
# exact character-by-character matching


def _try_simple_match(content: str, old_string: str) -> Optional[str]:
    """Try exact string match."""
    if old_string in content:
        return old_string
    return None


def _try_line_trimmed_match(content: str, old_string: str) -> Optional[str]:
    """Try matching lines where content is the same when trimmed."""
    content_lines = content.split("\n")
    search_lines = old_string.split("\n")

    # Remove trailing empty line if present in search
    if search_lines and search_lines[-1] == "":
        search_lines.pop()

    # Scan through content looking for matching block
    for i in range(len(content_lines) - len(search_lines) + 1):
        matches = True
        for j, search_line in enumerate(search_lines):
            if content_lines[i + j].strip() != search_line.strip():
                matches = False
                break

        if matches:
            # Found a match - return the original lines (with indentation) joined
            matched_lines = content_lines[i : i + len(search_lines)]
            result = "\n".join(matched_lines)

            # Preserve trailing newlines if present in the matched section
            # After the matched lines, check if there's more content (indicating trailing newline)
            end_index = i + len(search_lines)
            if end_index < len(content_lines):
                # There's more content after match, so add the newline that separates them
                result += "\n"
            elif content.endswith("\n"):
                # At end of file and file ends with newline, preserve it
                result += "\n"

            return result

    return None


def _try_whitespace_normalized_match(content: str, old_string: str) -> Optional[str]:
    """Try matching with normalized whitespace (all whitespace becomes single space)."""

    def normalize(text: str) -> str:
        return " ".join(text.split())

    normalized_search = normalize(old_string)

    # Try single line matches
    for line in content.split("\n"):
        if normalize(line) == normalized_search:
            return line

    # Try multi-line matches
    search_lines = old_string.split("\n")
    if len(search_lines) > 1:
        content_lines = content.split("\n")
        for i in range(len(content_lines) - len(search_lines) + 1):
            block_lines = content_lines[i : i + len(search_lines)]
            if normalize("\n".join(block_lines)) == normalized_search:
                return "\n".join(block_lines)

    return None


def _find_match_with_strategies(content: str, old_string: str) -> Optional[str]:
    """
    Try multiple matching strategies in order.
    Returns the matched string from content (preserving original formatting).
    """
    # Strategy 1: Exact match (but only if it's not a substring that would match better with trimming)
    # Skip exact match if old_string doesn't have leading/trailing whitespace
    # and we're searching for what looks like a complete statement
    use_exact = old_string in content

    # If the old_string has no leading whitespace but contains a newline or looks like code,
    # skip exact match and try trimmed matching first
    if use_exact and not old_string.startswith((" ", "\t", "\n")):
        # Check if this looks like we're searching for a line of code
        # (contains common code patterns but no leading indentation)
        code_patterns = [
            "(",
            ")",
            "=",
            "def ",
            "class ",
            "if ",
            "for ",
            "while ",
            "return ",
            "print(",
        ]
        if any(pattern in old_string for pattern in code_patterns):
            # Try trimmed match first for code-like patterns
            match = _try_line_trimmed_match(content, old_string)
            if match:
                return match

    # Now try exact match
    match = _try_simple_match(content, old_string)
    if match:
        return match

    # Strategy 2: Line-trimmed match (handles indentation differences)
    match = _try_line_trimmed_match(content, old_string)
    if match:
        return match

    # Strategy 3: Whitespace-normalized match (handles spacing differences)
    match = _try_whitespace_normalized_match(content, old_string)
    if match:
        return match

    return None


# ============================================================================


def apply_patch(path: str, new_content: str) -> str:
    """
    Apply changes to a file by replacing its contents.

    Args:
        path: Relative path to the file from the repository root
        new_content: The new complete content for the file

    Returns:
        A confirmation message with the unified diff

    Raises:
        ValueError: If in read-only mode or file is too large
    """
    _operation_limiter.check_limit(f"apply_patch({path})")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot modify files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=False)

    # Check size of new content
    new_size = len(new_content.encode("utf-8"))
    if new_size > MAX_FILE_SIZE:
        raise ValueError(f"New content too large: {new_size:,} bytes (max {MAX_FILE_SIZE:,} bytes)")

    # Read old content if file exists (needed for diff in permission prompt)
    old_content = ""
    if p.exists():
        with open(p, "r", encoding="utf-8", errors="surrogateescape", newline=None) as f:
            old_content = f.read()
        old = old_content.splitlines(keepends=True)
    else:
        old = []

    # Check permission with colored diff
    permission_manager = _get_permission_manager()
    operation = "Create" if not p.exists() else "Update"
    diff_display = _format_colored_diff(old_content, new_content, file_path=path)

    # Get permission pattern (directory for outside repo, relative path for inside)
    permission_pattern = _get_permission_pattern_for_path(path, p)

    # Add warning if writing outside repository (unless it's PatchPal's managed files)
    outside_repo_warning = _get_outside_repo_warning(p)

    description = f"   ● {operation}({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission(
        "apply_patch", description, pattern=permission_pattern
    ):
        return "Operation cancelled by user."

    # Check git status for uncommitted changes (only for files inside repo)
    git_status = _check_git_status()
    git_warning = ""
    if _is_inside_repo(p) and git_status.get("is_repo") and git_status.get("has_uncommitted"):
        relative_path = str(p.relative_to(common.REPO_ROOT))
        if any(relative_path in change for change in git_status.get("changes", [])):
            git_warning = "\n⚠️  Note: File has uncommitted changes in git\n"

    # Backup existing file
    backup_path = None
    if p.exists():
        backup_path = _backup_file(p)

    new = new_content.splitlines(keepends=True)

    # Generate diff
    diff = difflib.unified_diff(
        old,
        new,
        fromfile=f"{path} (before)",
        tofile=f"{path} (after)",
    )
    diff_str = "".join(diff)

    # Check if critical file
    warning = ""
    if _is_critical_file(p):
        warning = "\n⚠️  WARNING: Modifying critical infrastructure file!\n"

    # Write the new content
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
        f.write(new_content)

    # Audit log
    audit_logger.info(
        f"WRITE: {path} ({new_size} bytes)" + (f" [BACKUP: {backup_path}]" if backup_path else "")
    )

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""

    return f"Successfully updated {path}{warning}{git_warning}{backup_msg}\n\nDiff:\n{diff_str}"


def edit_file(path: str, old_string: str, new_string: str) -> str:
    """
    Edit a file by replacing a string match with flexible whitespace handling.

    Uses multiple matching strategies to find old_string:
    1. Exact match
    2. Trimmed line match (ignores indentation differences in search)
    3. Normalized whitespace match (ignores spacing differences in search)

    Important: The flexible matching only applies to FINDING old_string.
    The new_string is used exactly as provided, so it should include proper
    indentation/formatting to match the surrounding code.

    Args:
        path: Relative path to the file from the repository root
        old_string: The string to find (whitespace can be approximate)
        new_string: The replacement string (use exact whitespace/indentation you want)

    Returns:
        Confirmation message with the changes made

    Raises:
        ValueError: If file not found, old_string not found, or multiple matches

    Example:
        # Find with flexible matching, but provide new_string with proper indent
        edit_file("test.py", "print('hello')", "    print('world')")  # 4 spaces
    """
    _operation_limiter.check_limit(f"edit_file({path[:30]}...)")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot edit files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=True)

    # Read current content
    try:
        with open(p, "r", encoding="utf-8", errors="surrogateescape", newline=None) as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

    # Try to find a match using multiple strategies
    matched_string = _find_match_with_strategies(content, old_string)

    if not matched_string:
        # No match found with any strategy
        raise ValueError(
            f"String not found in {path}.\n\n"
            f"Searched for:\n{old_string[:200]}\n\n"
            f"💡 Tip: Use read_lines() to see exact content, or use apply_patch() for larger changes."
        )

    # Count occurrences of the matched string
    count = content.count(matched_string)
    if count > 1:
        # Show WHERE the matches are
        positions = []
        start = 0
        while True:
            pos = content.find(matched_string, start)
            if pos == -1:
                break
            line_num = content[:pos].count("\n") + 1
            positions.append(line_num)
            start = pos + 1

        raise ValueError(
            f"String appears {count} times in {path} at lines: {positions}\n"
            f"Add more context (3-5 surrounding lines) to make it unique.\n\n"
            f"💡 Tip: Use read_lines() to see the exact context, or use apply_patch() for multiple changes."
        )

    # Perform indentation adjustment and trailing newline preservation BEFORE showing diff
    # Important: Adjust indentation and preserve trailing newlines to maintain file structure
    adjusted_new_string = new_string

    # Step 1: Adjust indentation if needed
    # Get the indentation of the first line in matched_string vs new_string
    matched_lines = matched_string.split("\n")
    new_lines = new_string.split("\n")

    if matched_lines and new_lines and matched_lines[0] and new_lines[0]:
        # Get leading whitespace of first line in matched string
        matched_indent = len(matched_lines[0]) - len(matched_lines[0].lstrip())
        new_indent = len(new_lines[0]) - len(new_lines[0].lstrip())

        if matched_indent != new_indent:
            # Need to adjust indentation
            indent_diff = matched_indent - new_indent

            # Apply the indentation adjustment to all non-empty lines in new_string
            adjusted_lines = []
            for line in new_lines:
                if line.strip():  # Non-empty line
                    if indent_diff > 0:
                        # Need to add spaces
                        adjusted_lines.append((" " * indent_diff) + line)
                    else:
                        # Need to remove spaces (if possible)
                        spaces_to_remove = abs(indent_diff)
                        if line[:spaces_to_remove].strip() == "":  # All spaces
                            adjusted_lines.append(line[spaces_to_remove:])
                        else:
                            # Can't remove that many spaces, keep as-is
                            adjusted_lines.append(line)
                else:
                    # Empty line, keep as-is
                    adjusted_lines.append(line)

            adjusted_new_string = "\n".join(adjusted_lines)

    # Step 2: Preserve trailing newlines from matched_string
    if matched_string.endswith("\n") and not adjusted_new_string.endswith("\n"):
        # Matched block had trailing newline(s), preserve them
        # Count consecutive trailing newlines in matched_string
        trailing_newlines = len(matched_string) - len(matched_string.rstrip("\n"))
        adjusted_new_string = adjusted_new_string + ("\n" * trailing_newlines)

    # Check permission before proceeding (use adjusted_new_string for accurate diff display)
    permission_manager = _get_permission_manager()

    # Format colored diff for permission prompt (use adjusted_new_string so user sees what will actually be written)
    diff_display = _format_colored_diff(matched_string, adjusted_new_string, file_path=path)

    # Get permission pattern (directory for outside repo, relative path for inside)
    permission_pattern = _get_permission_pattern_for_path(path, p)

    # Add warning if writing outside repository (unless it's PatchPal's managed files)
    outside_repo_warning = _get_outside_repo_warning(p)

    description = f"   ● Update({path}){outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission(
        "edit_file", description, pattern=permission_pattern
    ):
        return "Operation cancelled by user."

    # Backup if enabled
    backup_path = _backup_file(p)

    new_content = content.replace(matched_string, adjusted_new_string)

    # Write the new content
    with open(p, "w", encoding="utf-8", errors="surrogateescape", newline="\n") as f:
        f.write(new_content)

    # Generate diff for the specific change (use adjusted_new_string for accurate diff)
    old_lines = matched_string.split("\n")
    new_lines = adjusted_new_string.split("\n")
    diff = difflib.unified_diff(old_lines, new_lines, fromfile="old", tofile="new", lineterm="")
    diff_str = "\n".join(diff)

    audit_logger.info(f"EDIT: {path} ({len(matched_string)} -> {len(adjusted_new_string)} chars)")

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""
    return f"Successfully edited {path}{backup_msg}\n\nChange:\n{diff_str}"


def edit_file_hashline(
    path: str,
    edits: List[
        Union[
            dict,  # For JSON-serialized edits from LLM
            SetEdit,
            ReplaceEdit,
            AppendEdit,
            PrependEdit,
            InsertEdit,
        ]
    ],
) -> str:
    """
    Edit a file using hashline-based line references for precise, stable edits.

    This uses content hashes to verify line identity, preventing edits from being
    applied to the wrong location if the file changed since it was last read.

    Hashline format: Each line is identified as "LINE#HASH" where:
    - LINE is the 1-indexed line number
    - HASH is a 2-character content hash

    Supported operations:
    - set: Replace a single line
      {"op": "set", "tag": "5#AA", "content": ["new line"]}

    - replace: Replace a range of lines
      {"op": "replace", "first": "5#AA", "last": "7#BB", "content": ["new", "lines"]}

    - append: Append lines after a specific line (or at EOF if no 'after')
      {"op": "append", "after": "5#AA", "content": ["new lines"]}
      {"op": "append", "content": ["append at EOF"]}

    - prepend: Prepend lines before a specific line (or at BOF if no 'before')
      {"op": "prepend", "before": "5#AA", "content": ["new lines"]}
      {"op": "prepend", "content": ["prepend at BOF"]}

    - insert: Insert lines between two specific lines
      {"op": "insert", "after": "5#AA", "before": "6#BB", "content": ["new line"]}

    Args:
        path: Relative path to the file from the repository root
        edits: List of edit operations (dicts or Edit objects)

    Returns:
        Confirmation message with changes made

    Raises:
        ValueError: If file not found or edit operations invalid
        HashlineMismatchError: If line hashes don't match (file changed since last read)

    Example:
        # Read file first to get line hashes:
        # 1#ZP:def foo():
        # 2#MQ:    return 42
        # 3#VR:

        edit_file_hashline("test.py", [
            {"op": "set", "tag": "2#MQ", "content": ["    return 100"]}
        ])
    """
    _operation_limiter.check_limit(f"edit_file_hashline({path[:30]}...)")

    if READ_ONLY_MODE:
        raise ValueError(
            "Cannot edit files in read-only mode\n"
            "Set PATCHPAL_READ_ONLY=false to allow modifications"
        )

    p = _check_path(path, must_exist=True)

    # Read current content
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

    # Convert dict edits to proper Edit objects
    edit_objects: List[Union[SetEdit, ReplaceEdit, AppendEdit, PrependEdit, InsertEdit]] = []

    for edit in edits:
        if isinstance(edit, dict):
            op = edit.get("op")

            if op == "set":
                tag = parse_tag(edit["tag"])
                content_lines = edit.get("content", [])
                if isinstance(content_lines, str):
                    content_lines = [content_lines]
                edit_objects.append(SetEdit(tag=tag, content=content_lines))

            elif op == "replace":
                first = parse_tag(edit["first"])
                last = parse_tag(edit["last"])
                content_lines = edit.get("content", [])
                if isinstance(content_lines, str):
                    content_lines = [content_lines]
                edit_objects.append(ReplaceEdit(first=first, last=last, content=content_lines))

            elif op == "append":
                after = parse_tag(edit["after"]) if "after" in edit else None
                content_lines = edit.get("content", [])
                if isinstance(content_lines, str):
                    content_lines = [content_lines]
                edit_objects.append(AppendEdit(content=content_lines, after=after))

            elif op == "prepend":
                before = parse_tag(edit["before"]) if "before" in edit else None
                content_lines = edit.get("content", [])
                if isinstance(content_lines, str):
                    content_lines = [content_lines]
                edit_objects.append(PrependEdit(content=content_lines, before=before))

            elif op == "insert":
                after = parse_tag(edit["after"])
                before = parse_tag(edit["before"])
                content_lines = edit.get("content", [])
                if isinstance(content_lines, str):
                    content_lines = [content_lines]
                edit_objects.append(InsertEdit(after=after, before=before, content=content_lines))

            else:
                raise ValueError(f"Unknown edit operation: {op}")

        else:
            # Already an Edit object
            edit_objects.append(edit)

    if not edit_objects:
        raise ValueError("No edits provided")

    # Apply edits (this validates line hashes and applies changes)
    try:
        result: EditResult = apply_hashline_edits(content, edit_objects)
    except HashlineMismatchError as e:
        # Re-raise with more context
        raise HashlineMismatchError(e.mismatches, e.file_lines) from None

    # Check if anything actually changed
    if result.content == content:
        return f"No changes made to {path} - edits produced identical content."

    # Generate diff for permission check and display
    old_lines = content.splitlines(keepends=True)
    new_lines = result.content.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines, new_lines, fromfile=f"{path} (before)", tofile=f"{path} (after)"
    )
    diff_str = "".join(diff)

    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    diff_display = _format_colored_diff(content, result.content, file_path=path)

    # Get permission pattern (directory for outside repo, relative path for inside)
    permission_pattern = _get_permission_pattern_for_path(path, p)

    # Add warning if writing outside repository (unless it's PatchPal's managed files)
    outside_repo_warning = _get_outside_repo_warning(p)

    description = f"   ● Update({path}) [hashline edit]{outside_repo_warning}\n{diff_display}"

    if not permission_manager.request_permission(
        "edit_file_hashline", description, pattern=permission_pattern
    ):
        return "Operation cancelled by user."

    # Check git status for uncommitted changes
    git_status = _check_git_status()
    git_warning = ""
    if _is_inside_repo(p) and git_status.get("is_repo") and git_status.get("has_uncommitted"):
        relative_path = str(p.relative_to(common.REPO_ROOT))
        if any(relative_path in change for change in git_status.get("changes", [])):
            git_warning = "\n⚠️  Note: File has uncommitted changes in git\n"

    # Backup existing file
    backup_path = _backup_file(p)

    # Write the new content
    p.write_text(result.content)

    # Check if critical file
    warning = ""
    if _is_critical_file(p):
        warning = "\n⚠️  WARNING: Modifying critical infrastructure file!\n"

    audit_logger.info(
        f"HASHLINE_EDIT: {path} ({len(edit_objects)} edits, {len(content)} -> {len(result.content)} bytes)"
    )

    backup_msg = f"\n[Backup saved: {backup_path}]" if backup_path else ""
    edit_summary = f"{len(edit_objects)} edit{'s' if len(edit_objects) > 1 else ''}"

    return f"Successfully applied {edit_summary} to {path}{warning}{git_warning}{backup_msg}\n\nDiff:\n{diff_str}"
