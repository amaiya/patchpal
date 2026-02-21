"""
Hashline edit mode — a line-addressable edit format using content hashes.

Each line in a file is identified by its 1-indexed line number and a short
hexadecimal hash derived from the normalized line content (xxHash32, truncated to 2
hex chars).

The combined `LINE#ID` reference acts as both an address and a staleness check:
if the file has changed since the caller last read it, hash mismatches are caught
before any mutation occurs.

Displayed format: `LINENUM#HASH:CONTENT`
Reference format: `"LINENUM#HASH"` (e.g. `"5#aa"`)

Based on the hashline implementation from oh-my-pi by Can Bölük.
Blog post: https://blog.can.ac/2026/02/12/the-harness-problem/
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

import xxhash

# Nibble mapping for hash encoding (same as oh-my-pi)
NIBBLE_STR = "ZPMQVRWSNKTXJBYH"

# Pre-computed dictionary for fast hash encoding
HASH_DICT = [f"{NIBBLE_STR[i >> 4]}{NIBBLE_STR[i & 0x0F]}" for i in range(256)]


@dataclass
class LineTag:
    """A line reference with line number and content hash."""

    line: int  # 1-indexed line number
    hash: str  # 2-character hash


@dataclass
class HashMismatch:
    """Represents a hash mismatch at a specific line."""

    line: int
    expected: str  # Hash provided by caller
    actual: str  # Hash computed from file


class HashlineMismatchError(Exception):
    """Error thrown when line references have stale hashes."""

    def __init__(self, mismatches: List[HashMismatch], file_lines: List[str]):
        self.mismatches = mismatches
        self.file_lines = file_lines
        self.remaps = {}
        for m in mismatches:
            actual_hash = compute_line_hash(m.line, file_lines[m.line - 1])
            self.remaps[f"{m.line}#{m.expected}"] = f"{m.line}#{actual_hash}"

        message = self._format_message(mismatches, file_lines)
        super().__init__(message)

    @staticmethod
    def _format_message(mismatches: List[HashMismatch], file_lines: List[str]) -> str:
        """Format error message with context around mismatched lines."""
        context_lines = 2  # Lines of context above/below

        mismatch_map = {m.line: m for m in mismatches}

        # Collect line numbers to display (mismatch lines + context)
        display_lines = set()
        for m in mismatches:
            lo = max(1, m.line - context_lines)
            hi = min(len(file_lines), m.line + context_lines)
            for i in range(lo, hi + 1):
                display_lines.add(i)

        sorted_lines = sorted(display_lines)

        lines = [
            f"{len(mismatches)} line{'s have' if len(mismatches) > 1 else ' has'} changed since last read. "
            f"Use the updated LINE#ID references shown below (>>> marks changed lines).",
            "",
        ]

        prev_line = -1
        for line_num in sorted_lines:
            # Gap separator for non-contiguous regions
            if prev_line != -1 and line_num > prev_line + 1:
                lines.append("    ...")
            prev_line = line_num

            content = file_lines[line_num - 1]
            hash_val = compute_line_hash(line_num, content)
            prefix = f"{line_num}#{hash_val}"

            if line_num in mismatch_map:
                lines.append(f">>> {prefix}:{content}")
            else:
                lines.append(f"    {prefix}:{content}")

        return "\n".join(lines)


def compute_line_hash(idx: int, line: str) -> str:
    """
    Compute a short hexadecimal hash of a single line.

    Uses xxHash32 on a whitespace-normalized line, truncated to 2 hex characters.
    The line input should not include a trailing newline.

    Args:
        idx: Line number (currently not used in hash, for API compatibility)
        line: Line content (without trailing newline)

    Returns:
        2-character hash string from NIBBLE_STR alphabet
    """
    # Remove trailing carriage return if present
    if line.endswith("\r"):
        line = line[:-1]

    # Normalize whitespace (like oh-my-pi does)
    normalized = re.sub(r"\s+", "", line)

    # Compute xxHash32 and take lowest byte
    hash_val = xxhash.xxh32(normalized.encode("utf-8")).intdigest()
    byte_val = hash_val & 0xFF

    return HASH_DICT[byte_val]


def format_hash_lines(content: str, start_line: int = 1) -> str:
    """
    Format file content with hashline prefixes for display.

    Each line becomes `LINENUM#HASH:CONTENT` where LINENUM is 1-indexed.

    Args:
        content: Raw file content string
        start_line: First line number (1-indexed, defaults to 1)

    Returns:
        Formatted string with one hashline-prefixed line per input line

    Example:
        >>> format_hash_lines("function hi() {\\n  return;\\n}")
        "1#HH:function hi() {\\n2#HH:  return;\\n3#HH:}"
    """
    lines = content.split("\n")
    result = []
    for i, line in enumerate(lines):
        num = start_line + i
        hash_val = compute_line_hash(num, line)
        result.append(f"{num}#{hash_val}:{line}")
    return "\n".join(result)


def parse_tag(ref: str) -> LineTag:
    """
    Parse a line reference string like `"5#aa"` into structured form.

    Args:
        ref: Line reference string (format: "LINE#HASH")

    Returns:
        LineTag with line number and hash

    Raises:
        ValueError: If format is invalid
    """
    # Regex captures:
    #  1. optional leading markers (>+- and whitespace)
    #  2. line number (1+ digits)
    #  3. "#" with optional surrounding spaces
    #  4. hash (2 chars from NIBBLE_STR)
    #  5. optional trailing display suffix (":..." or "  ...")
    pattern = r"^\s*[>+\-]*\s*(\d+)\s*#\s*([" + NIBBLE_STR + "]{2})"
    match = re.match(pattern, ref)

    if not match:
        raise ValueError(
            f'Invalid line reference "{ref}". Expected format "LINE#ID" (e.g. "5#aa").'
        )

    line = int(match.group(1))
    if line < 1:
        raise ValueError(f'Line number must be >= 1, got {line} in "{ref}".')

    hash_val = match.group(2)
    return LineTag(line=line, hash=hash_val)


def validate_line_ref(ref: LineTag, file_lines: List[str]) -> None:
    """
    Validate that a line reference points to an existing line with a matching hash.

    Args:
        ref: Parsed line reference (1-indexed line number + expected hash)
        file_lines: Array of file lines (0-indexed)

    Raises:
        ValueError: If line is out of range
        HashlineMismatchError: If hash doesn't match (includes correct hashes in context)
    """
    if ref.line < 1 or ref.line > len(file_lines):
        raise ValueError(f"Line {ref.line} does not exist (file has {len(file_lines)} lines)")

    actual_hash = compute_line_hash(ref.line, file_lines[ref.line - 1])
    if actual_hash != ref.hash:
        raise HashlineMismatchError(
            [HashMismatch(line=ref.line, expected=ref.hash, actual=actual_hash)], file_lines
        )


@dataclass
class HashlineEdit:
    """Base class for hashline edit operations."""

    pass


@dataclass
class SetEdit(HashlineEdit):
    """Replace a single line."""

    tag: LineTag
    content: List[str]


@dataclass
class ReplaceEdit(HashlineEdit):
    """Replace a range of lines."""

    first: LineTag
    last: LineTag
    content: List[str]


@dataclass
class AppendEdit(HashlineEdit):
    """Append lines after a specific line or at EOF."""

    content: List[str]
    after: Optional[LineTag] = None  # If None, append at EOF


@dataclass
class PrependEdit(HashlineEdit):
    """Prepend lines before a specific line or at BOF."""

    content: List[str]
    before: Optional[LineTag] = None  # If None, prepend at BOF


@dataclass
class InsertEdit(HashlineEdit):
    """Insert lines between two specific lines."""

    after: LineTag
    before: LineTag
    content: List[str]


@dataclass
class EditResult:
    """Result of applying hashline edits."""

    content: str
    first_changed_line: Optional[int] = None
    warnings: Optional[List[str]] = None
    noop_edits: Optional[List[dict]] = None


def apply_hashline_edits(content: str, edits: List[HashlineEdit]) -> EditResult:
    """
    Apply an array of hashline edits to file content.

    Each edit operation identifies target lines directly (set, replace, insert, append, prepend).
    Line references are resolved and hashes validated before any mutation.

    Edits are sorted bottom-up (highest effective line first) so earlier
    splices don't invalidate later line numbers.

    Args:
        content: Original file content
        edits: List of edit operations to apply

    Returns:
        EditResult with modified content and metadata

    Raises:
        HashlineMismatchError: If any line hash doesn't match current file
        ValueError: For invalid edit operations
    """
    if not edits:
        return EditResult(content=content, first_changed_line=None)

    file_lines = content.split("\n")
    first_changed_line = None

    # Pre-validate: collect all hash mismatches before mutating
    mismatches: List[HashMismatch] = []

    def validate_ref(ref: LineTag) -> bool:
        """Validate a line reference, recording mismatches."""
        if ref.line < 1 or ref.line > len(file_lines):
            raise ValueError(f"Line {ref.line} does not exist (file has {len(file_lines)} lines)")

        actual_hash = compute_line_hash(ref.line, file_lines[ref.line - 1])
        if actual_hash == ref.hash:
            return True

        mismatches.append(HashMismatch(line=ref.line, expected=ref.hash, actual=actual_hash))
        return False

    # Validate all line references
    for edit in edits:
        if isinstance(edit, SetEdit):
            validate_ref(edit.tag)
        elif isinstance(edit, ReplaceEdit):
            if edit.first.line > edit.last.line:
                raise ValueError(
                    f"Range start line {edit.first.line} must be <= end line {edit.last.line}"
                )
            validate_ref(edit.first)
            validate_ref(edit.last)
        elif isinstance(edit, AppendEdit):
            if edit.after:
                validate_ref(edit.after)
        elif isinstance(edit, PrependEdit):
            if edit.before:
                validate_ref(edit.before)
        elif isinstance(edit, InsertEdit):
            if edit.before.line <= edit.after.line:
                raise ValueError(
                    f"insert requires after ({edit.after.line}) < before ({edit.before.line})"
                )
            validate_ref(edit.after)
            validate_ref(edit.before)

    if mismatches:
        raise HashlineMismatchError(mismatches, file_lines)

    # Compute sort key (descending) — bottom-up application
    def get_sort_key(edit: HashlineEdit) -> Tuple[int, int]:
        """Return (sort_line, precedence) for sorting edits bottom-up."""
        if isinstance(edit, SetEdit):
            return (edit.tag.line, 0)
        elif isinstance(edit, ReplaceEdit):
            return (edit.last.line, 0)
        elif isinstance(edit, AppendEdit):
            return (edit.after.line if edit.after else len(file_lines) + 1, 1)
        elif isinstance(edit, PrependEdit):
            return (edit.before.line if edit.before else 0, 2)
        elif isinstance(edit, InsertEdit):
            return (edit.before.line, 3)
        return (0, 99)  # Shouldn't happen

    # Sort edits bottom-up
    sorted_edits = sorted(edits, key=lambda e: (-get_sort_key(e)[0], get_sort_key(e)[1]))

    # Apply edits bottom-up
    for edit in sorted_edits:
        if isinstance(edit, SetEdit):
            # Replace single line
            file_lines[edit.tag.line - 1 : edit.tag.line] = edit.content
            if first_changed_line is None or edit.tag.line < first_changed_line:
                first_changed_line = edit.tag.line

        elif isinstance(edit, ReplaceEdit):
            # Replace range of lines
            count = edit.last.line - edit.first.line + 1
            file_lines[edit.first.line - 1 : edit.first.line - 1 + count] = edit.content
            if first_changed_line is None or edit.first.line < first_changed_line:
                first_changed_line = edit.first.line

        elif isinstance(edit, AppendEdit):
            # Append lines after a specific line or at EOF
            if edit.after:
                file_lines[edit.after.line : edit.after.line] = edit.content
                if first_changed_line is None or edit.after.line + 1 < first_changed_line:
                    first_changed_line = edit.after.line + 1
            else:
                # Append at EOF
                if len(file_lines) == 1 and file_lines[0] == "":
                    file_lines = edit.content
                    first_changed_line = 1
                else:
                    file_lines.extend(edit.content)
                    if first_changed_line is None:
                        first_changed_line = len(file_lines) - len(edit.content) + 1

        elif isinstance(edit, PrependEdit):
            # Prepend lines before a specific line or at BOF
            if edit.before:
                file_lines[edit.before.line - 1 : edit.before.line - 1] = edit.content
                if first_changed_line is None or edit.before.line < first_changed_line:
                    first_changed_line = edit.before.line
            else:
                # Prepend at BOF
                if len(file_lines) == 1 and file_lines[0] == "":
                    file_lines = edit.content
                else:
                    file_lines = edit.content + file_lines
                first_changed_line = 1

        elif isinstance(edit, InsertEdit):
            # Insert lines between two lines
            file_lines[edit.before.line - 1 : edit.before.line - 1] = edit.content
            if first_changed_line is None or edit.before.line < first_changed_line:
                first_changed_line = edit.before.line

    return EditResult(content="\n".join(file_lines), first_changed_line=first_changed_line)
