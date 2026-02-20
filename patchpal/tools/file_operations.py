"""File operation tools (read, get info)."""

import mimetypes
import os
from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    MAX_FILE_SIZE,
    _check_path,
    _is_binary_file,
    _operation_limiter,
    audit_logger,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_pptx,
    require_permission_for_read,
)


@require_permission_for_read(
    "read_file", get_description=lambda path: f"   Read: {path}", get_pattern=lambda path: path
)
def read_file(path: str) -> str:
    """
    Read the contents of a file.

    Supports text files, images, and documents (PDF, DOCX, PPTX) with automatic processing.

    Args:
        path: Path to the file (relative to repository root or absolute)

    Returns:
        The file contents as a string (text extracted from documents, base64 for images)

    Raises:
        ValueError: If file is too large, unsupported binary format, or sensitive
    """
    _operation_limiter.check_limit(f"read_file({path})")

    p = _check_path(path)

    # Get file size and MIME type
    size = p.stat().st_size
    mime_type, _ = mimetypes.guess_type(str(p))
    ext = p.suffix.lower()

    # Image formats - return as base64 data URL for vision models
    image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg", ".ico"}
    if ext in image_extensions or (mime_type and mime_type.startswith("image/")):
        # For SVG, return as text since it's XML-based
        if ext == ".svg" or mime_type == "image/svg+xml":
            # SVG is text, so apply normal size limit
            if size > MAX_FILE_SIZE:
                raise ValueError(
                    f"SVG file too large: {size:,} bytes (max {MAX_FILE_SIZE:,} bytes)\n"
                    f"Set PATCHPAL_MAX_FILE_SIZE env var to increase"
                )
            content = p.read_text(encoding="utf-8", errors="replace")
            audit_logger.info(f"READ: {path} ({size} bytes, SVG as text)")
            return content

        # For raster images, allow larger files (up to 10MB) since they're for vision models
        # Vision APIs have their own limits and will resize as needed
        # Images are formatted as multimodal content by the agent, bypassing tool output truncation
        max_image_size = int(os.getenv("PATCHPAL_MAX_IMAGE_SIZE", 10 * 1024 * 1024))  # 10MB default
        if size > max_image_size:
            raise ValueError(
                f"Image file too large: {size:,} bytes (max {max_image_size:,} bytes)\n"
                f"Set PATCHPAL_MAX_IMAGE_SIZE env var to increase\n"
                f"Note: Most vision APIs resize images automatically, so smaller images are recommended"
            )

        # Encode as base64
        import base64

        content_bytes = p.read_bytes()
        b64_data = base64.b64encode(content_bytes).decode("utf-8")

        # Determine MIME type
        if mime_type:
            image_mime = mime_type
        elif ext == ".jpg" or ext == ".jpeg":
            image_mime = "image/jpeg"
        elif ext == ".png":
            image_mime = "image/png"
        elif ext == ".gif":
            image_mime = "image/gif"
        elif ext == ".bmp":
            image_mime = "image/bmp"
        elif ext == ".webp":
            image_mime = "image/webp"
        elif ext == ".ico":
            image_mime = "image/x-icon"
        else:
            image_mime = "image/png"  # fallback

        audit_logger.info(f"READ: {path} ({size} bytes, IMAGE {image_mime})")

        # Return IMAGE_DATA format that agent will convert to multimodal content
        # This bypasses tool output truncation limits (PATCHPAL_MAX_TOOL_OUTPUT_CHARS)
        return f"IMAGE_DATA:{image_mime}:{b64_data}"

    # For document formats (PDF/DOCX/PPTX), extract text first, then check extracted size
    # This allows large binary documents as long as the extracted text fits in context
    # Check both MIME type and extension (Windows doesn't always recognize Office formats)
    if (mime_type and "pdf" in mime_type) or ext == ".pdf":
        # Extract text from PDF (no size check on binary - check extracted text instead)
        content_bytes = p.read_bytes()
        text_content = extract_text_from_pdf(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, PDF)"
        )
        return text_content
    elif (mime_type and ("wordprocessingml" in mime_type or "msword" in mime_type)) or ext in (
        ".docx",
        ".doc",
    ):
        # Extract text from DOCX/DOC
        content_bytes = p.read_bytes()
        text_content = extract_text_from_docx(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, DOCX)"
        )
        return text_content
    elif (mime_type and ("presentationml" in mime_type or "ms-powerpoint" in mime_type)) or ext in (
        ".pptx",
        ".ppt",
    ):
        # Extract text from PPTX/PPT
        content_bytes = p.read_bytes()
        text_content = extract_text_from_pptx(content_bytes, source=str(path))
        audit_logger.info(
            f"READ: {path} ({size} bytes binary, {len(text_content)} chars text, PPTX)"
        )
        return text_content

    # For non-document files, check size before reading
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size:,} bytes (max {MAX_FILE_SIZE:,} bytes)\n"
            f"Set PATCHPAL_MAX_FILE_SIZE env var to increase"
        )

    # Check if binary (for non-document files)
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot read binary file: {path}\nType: {mime_type or 'unknown'}\n"
            f"Supported document formats: PDF, DOCX, PPTX"
        )

    # Read as text file
    content = p.read_text(encoding="utf-8", errors="replace")
    audit_logger.info(f"READ: {path} ({size} bytes)")
    return content


@require_permission_for_read(
    "read_lines",
    get_description=lambda path,
    start_line,
    end_line=None: f"   Read lines {start_line}-{end_line or start_line}: {path}",
    get_pattern=lambda path, start_line, end_line=None: path,
)
def read_lines(path: str, start_line: int, end_line: Optional[int] = None) -> str:
    """
    Read specific lines from a file.

    Args:
        path: Path to the file (relative to repository root or absolute)
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (inclusive, 1-indexed). If omitted, reads only start_line

    Returns:
        The requested lines with line numbers

    Raises:
        ValueError: If file not found, binary, sensitive, or line numbers invalid

    Examples:
        read_lines("src/auth.py", 45, 60)  # Read lines 45-60
        read_lines("src/auth.py", 45)       # Read only line 45

    Tip:
        Use `wc -l filename` shell command to find total line count for reading from end
    """
    _operation_limiter.check_limit(f"read_lines({path}, {start_line}-{end_line or start_line})")

    # Validate line numbers
    if start_line < 1:
        raise ValueError(f"start_line must be >= 1, got {start_line}")

    if end_line is None:
        end_line = start_line
    elif end_line < start_line:
        raise ValueError(f"end_line ({end_line}) must be >= start_line ({start_line})")

    p = _check_path(path)

    # Check if binary
    if _is_binary_file(p):
        raise ValueError(
            f"Cannot read binary file: {path}\nType: {mimetypes.guess_type(str(p))[0] or 'unknown'}"
        )

    # Read file and extract lines
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        raise ValueError(f"Failed to read file: {e}")

    total_lines = len(lines)

    # Check if line numbers are within range
    if start_line > total_lines:
        raise ValueError(f"start_line {start_line} exceeds file length ({total_lines} lines)")

    # Adjust end_line if it exceeds file length
    actual_end_line = min(end_line, total_lines)

    # Extract requested lines (convert to 0-indexed)
    requested_lines = lines[start_line - 1 : actual_end_line]

    # Format output with line numbers
    result = []
    for i, line in enumerate(requested_lines, start=start_line):
        # Remove trailing newline for cleaner output
        result.append(f"{i:4d}  {line.rstrip()}")

    output = "\n".join(result)

    # Add note if we truncated end_line
    if actual_end_line < end_line:
        output += (
            f"\n\n(Note: Requested lines up to {end_line}, but file only has {total_lines} lines)"
        )

    audit_logger.info(
        f"READ_LINES: {path} lines {start_line}-{actual_end_line} ({len(requested_lines)} lines)"
    )
    return output


@require_permission_for_read(
    "get_file_info",
    get_description=lambda path: f"   Get info: {path}",
    get_pattern=lambda path: path,
)
def get_file_info(path: str) -> str:
    """
    Get metadata for file(s) at the specified path.

    Args:
        path: Path to file, directory, or glob pattern (e.g., "tests/*.txt")
              Can be relative to repository root or absolute

    Returns:
        Formatted string with file metadata (name, size, modified time, type)
        For multiple files, returns one line per file

    Raises:
        ValueError: If no files found
    """
    _operation_limiter.check_limit(f"get_file_info({path[:30]}...)")

    # Handle glob patterns
    if "*" in path or "?" in path:
        # It's a glob pattern
        # Use glob to find matching files
        try:
            matches = list(common.REPO_ROOT.glob(path))
        except Exception as e:
            raise ValueError(f"Invalid glob pattern: {e}")

        if not matches:
            return f"No files found matching pattern: {path}"

        # Filter to files only
        files = [p for p in matches if p.is_file()]
        if not files:
            return f"No files found matching pattern: {path}"
    else:
        # Single path
        p = _check_path(path, must_exist=False)

        if not p.exists():
            return f"Path does not exist: {path}"

        if p.is_file():
            files = [p]
        elif p.is_dir():
            # List all files in directory (non-recursive)
            files = [f for f in p.iterdir() if f.is_file() and not f.name.startswith(".")]
            if not files:
                return f"No files found in directory: {path}"
        else:
            return f"Path is not a file or directory: {path}"

    # Format file information
    results = []
    for file_path in sorted(files):
        try:
            stat = file_path.stat()

            # Try to get relative path; if it fails (e.g., Windows short names),
            # use the file name or absolute path
            try:
                relative_path = file_path.relative_to(common.REPO_ROOT)
            except ValueError:
                # Can't compute relative path (e.g., Windows short name mismatch)
                # Try to compute it manually by resolving both paths
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = common.REPO_ROOT.resolve()
                    relative_path = resolved_file.relative_to(resolved_repo)
                except (ValueError, OSError):
                    # Last resort: just use the file name
                    relative_path = file_path.name

            # Format size
            size = stat.st_size
            if size < 1024:
                size_str = f"{size}B"
            elif size < 1024 * 1024:
                size_str = f"{size / 1024:.1f}KB"
            else:
                size_str = f"{size / (1024 * 1024):.1f}MB"

            # Format modification time
            from datetime import datetime

            mtime = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            # Detect file type
            if _is_binary_file(file_path):
                file_type = "binary"
            else:
                mime_type, _ = mimetypes.guess_type(str(file_path))
                file_type = mime_type or "text"

            results.append(f"{str(relative_path):<50} {size_str:>10}  {mtime}  {file_type}")

        except Exception as e:
            # Get relative path for error message (may fail if path is invalid)
            try:
                relative_path = file_path.relative_to(common.REPO_ROOT)
            except Exception:
                try:
                    resolved_file = file_path.resolve()
                    resolved_repo = common.REPO_ROOT.resolve()
                    relative_path = resolved_file.relative_to(resolved_repo)
                except Exception:
                    relative_path = file_path.name
            results.append(f"{str(relative_path):<50} ERROR: {e}")

    header = f"{'Path':<50} {'Size':>10}  {'Modified'}            {'Type'}"
    separator = "-" * 100

    output = f"{header}\n{separator}\n" + "\n".join(results)
    audit_logger.info(f"FILE_INFO: {path} - {len(files)} file(s)")
    return output
