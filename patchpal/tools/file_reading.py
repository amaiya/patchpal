"""File operation tools (read, get info)."""

import mimetypes
from typing import Optional

from patchpal.config import config
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
            with open(p, "r", encoding="utf-8", errors="surrogateescape", newline=None) as f:
                content = f.read()
            audit_logger.info(f"READ: {path} ({size} bytes, SVG as text)")
            return content

        # For raster images, allow larger files (up to 10MB) since they're for vision models
        # Vision APIs have their own limits and will resize as needed
        # Images are formatted as multimodal content by the agent, bypassing tool output truncation
        max_image_size = config.MAX_IMAGE_SIZE
        if size > max_image_size:
            raise ValueError(
                f"Image file too large: {size:,} bytes (max {max_image_size:,} bytes)\n"
                f"Set PATCHPAL_MAX_IMAGE_SIZE env var to increase\n"
                f"Note: Most vision APIs resize images automatically, so smaller images are recommended"
            )

        # Encode as base64
        import base64

        try:
            content_bytes = p.read_bytes()
            b64_data = base64.b64encode(content_bytes).decode("utf-8")
        except Exception as e:
            raise ValueError(
                f"Failed to read or encode image file '{path}': {e}\n"
                f"The file may be corrupted or inaccessible."
            )

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
    with open(p, "r", encoding="utf-8", errors="surrogateescape", newline=None) as f:
        content = f.read()
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
        with open(p, "r", encoding="utf-8", errors="surrogateescape", newline=None) as f:
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
