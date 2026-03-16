"""Find files tool for searching files by glob pattern.

This tool provides fast file searching using glob patterns, similar to fd.
Useful for read-only agents that need to explore the repository structure
without requiring run_shell access.
"""

import os
from pathlib import Path
from typing import Optional

from patchpal.tools.common import (
    REPO_ROOT,
    _operation_limiter,
    audit_logger,
    require_permission_for_read,
)

MAX_RESULTS = 100
MAX_OUTPUT_BYTES = 50 * 1024


@require_permission_for_read(
    "find",
    get_description=lambda pattern="**/*", path=None: (
        f"   Search for files matching '{pattern}'" + (f" in {path}" if path else "")
    ),
    get_pattern=lambda pattern="**/*", path=None: path,
)
def find(pattern: str = "**/*", path: Optional[str] = None) -> str:
    """Search for files by glob pattern.

    Returns matching file paths relative to the search directory, sorted by
    modification time (most recent first). Respects .gitignore patterns.

    Args:
        pattern: Glob pattern to match files (default: "**/*" for all files).
                 Examples: '*.py', '**/*.json', 'src/**/*.spec.ts'
        path: Directory to search in (default: repository root). Can be relative to repo root or absolute.

    Returns:
        Newline-separated list of matching file paths, sorted by modification time
    """
    _operation_limiter.check_limit(f"find({pattern})")

    # Determine search directory
    if path:
        expanded_path = os.path.expanduser(path)
        path_obj = Path(expanded_path)
        if path_obj.is_absolute():
            search_dir = path_obj.resolve()
        else:
            search_dir = (REPO_ROOT / expanded_path).resolve()

        if not search_dir.exists():
            raise ValueError(f"Path not found: {path}")

        if not search_dir.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
    else:
        search_dir = REPO_ROOT

    # Check if pattern requires recursive search
    if "**" in pattern:
        # Recursive glob
        matches = list(search_dir.glob(pattern))
    else:
        # Check if pattern contains path separators
        if "/" in pattern or "\\" in pattern:
            # Pattern includes directory structure
            matches = list(search_dir.glob(pattern))
        else:
            # Simple filename pattern - search recursively
            matches = list(search_dir.glob(f"**/{pattern}"))

    # Filter to only files
    matches = [p for p in matches if p.is_file()]

    # Load gitignore patterns if .gitignore exists
    gitignore_patterns = _load_gitignore_patterns(REPO_ROOT)

    # Filter out gitignored files
    filtered_matches = []
    for match in matches:
        if not _is_gitignored(match, REPO_ROOT, gitignore_patterns):
            filtered_matches.append(match)

    matches = filtered_matches

    # Collect files with modification times
    files_with_mtime = []
    for file_path in matches:
        try:
            mtime = file_path.stat().st_mtime
            # Relativize path
            try:
                rel_path = file_path.relative_to(REPO_ROOT)
            except ValueError:
                # File is outside repo root
                rel_path = file_path.relative_to(search_dir)
            files_with_mtime.append((str(rel_path), mtime))
        except OSError:
            # Skip files we can't stat
            continue

    # Sort by modification time (most recent first)
    files_with_mtime.sort(key=lambda x: x[1], reverse=True)

    # Limit results
    truncated = len(files_with_mtime) > MAX_RESULTS
    files_with_mtime = files_with_mtime[:MAX_RESULTS]

    # Extract just the paths
    result_files = [f[0] for f in files_with_mtime]

    audit_logger.info(
        f"FIND: Found {len(result_files)} files matching '{pattern}' in {path or 'repository'}"
    )

    if not result_files:
        return "No files found matching pattern"

    result_text = "\n".join(result_files)

    if truncated:
        result_text += f"\n\n[{MAX_RESULTS} results limit reached; refine the pattern for more specific results]"

    # Truncate if output is too large
    if len(result_text.encode("utf-8")) > MAX_OUTPUT_BYTES:
        result_text = result_text[: MAX_OUTPUT_BYTES // 2] + "\n\n[output truncated]"

    return result_text


def _load_gitignore_patterns(repo_root: Path) -> list:
    """Load patterns from .gitignore file."""
    gitignore_path = repo_root / ".gitignore"
    patterns = []

    if not gitignore_path.exists():
        return patterns

    try:
        with open(gitignore_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # Skip empty lines and comments
                if line and not line.startswith("#"):
                    patterns.append(line)
    except Exception:
        # If we can't read .gitignore, just continue without it
        pass

    return patterns


def _is_gitignored(file_path: Path, repo_root: Path, patterns: list) -> bool:
    """Check if a file matches any gitignore pattern."""
    if not patterns:
        return False

    try:
        rel_path = file_path.relative_to(repo_root)
    except ValueError:
        # File is outside repo root
        return False

    rel_path_str = str(rel_path)
    parts = rel_path.parts

    for pattern in patterns:
        # Skip negation patterns (we're doing simple matching)
        if pattern.startswith("!"):
            continue

        # Remove trailing slash
        pattern = pattern.rstrip("/")

        # Check for directory-only patterns
        if pattern.endswith("/"):
            pattern = pattern.rstrip("/")
            # Check if any parent directory matches
            for part in parts[:-1]:  # Exclude filename
                if _match_pattern(part, pattern):
                    return True
        else:
            # Match against full path or any path component
            if _match_pattern(rel_path_str, pattern):
                return True
            # Also check if pattern matches any directory name
            for part in parts:
                if _match_pattern(part, pattern):
                    return True

    return False


def _match_pattern(text: str, pattern: str) -> bool:
    """Simple glob pattern matching."""
    # Convert glob pattern to something we can match
    if "**" in pattern:
        # Recursive pattern
        pattern = pattern.replace("**", "*")

    if "*" in pattern:
        # Use Path.match for glob patterns
        return Path(text).match(pattern)
    else:
        # Exact match
        return text == pattern or text.endswith(f"/{pattern}")
