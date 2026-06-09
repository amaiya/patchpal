"""Repository map generation for efficient codebase exploration.

This module provides a compact overview of the entire repository structure,
showing function and class signatures from all files. Much more token-efficient
than reading individual files.

Inspired by aider's repomap feature, optimized for PatchPal's architecture.
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from patchpal.tools.code_analysis import LANGUAGE_MAP, code_structure
from patchpal.tools.common import REPO_ROOT, _operation_limiter, depth_limited_walk


class RepoMapCache:
    """Simple in-memory cache for repository map data with mtime tracking."""

    def __init__(self):
        self.cache: Dict[str, Tuple[float, str]] = {}  # path -> (mtime, structure)
        self.last_full_scan: float = 0  # Track when we last scanned the repo

    def get(self, path: Path) -> Optional[str]:
        """Get cached structure if file hasn't changed.

        Args:
            path: Path to the file

        Returns:
            Cached structure string if valid, None otherwise
        """
        try:
            mtime = path.stat().st_mtime
            cache_key = str(path)
            if cache_key in self.cache:
                cached_mtime, structure = self.cache[cache_key]
                if cached_mtime == mtime:
                    return structure
        except Exception:
            pass
        return None

    def set(self, path: Path, structure: str):
        """Cache structure with mtime.

        Args:
            path: Path to the file
            structure: Formatted structure string to cache
        """
        try:
            mtime = path.stat().st_mtime
            self.cache[str(path)] = (mtime, structure)
        except Exception:
            pass

    def should_rescan(self, max_age_seconds: float = 60) -> bool:
        """Check if enough time has passed to warrant a full rescan.

        Args:
            max_age_seconds: Maximum age in seconds before rescan (default: 60)

        Returns:
            True if we should rescan the repository
        """
        return (time.time() - self.last_full_scan) > max_age_seconds

    def mark_scanned(self):
        """Mark that we just completed a full repository scan."""
        self.last_full_scan = time.time()


# Global cache instance
_REPO_MAP_CACHE = RepoMapCache()


def get_repo_map(
    max_files: int = 100,
    include_patterns: Optional[List[str]] = None,
    exclude_patterns: Optional[List[str]] = None,
    focus_files: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
) -> str:
    """Generate a compact repository map showing code structure across all files.

    This provides a bird's-eye view of the codebase, showing function and class
    signatures without their implementations. Much more token-efficient than
    reading individual files.

    Supports 20+ languages including Python, JavaScript, TypeScript, Go, Rust,
    Java, C/C++, C#, Ruby, PHP, Swift, Kotlin, Scala, Elm, Elixir, and more.

    Args:
        max_files: Maximum number of files to include (default: 100)
        include_patterns: Glob patterns to include (e.g., ['*.py', '*.js'])
        exclude_patterns: Glob patterns to exclude (e.g., ['*test*', '*_pb2.py'])
        focus_files: Files mentioned in conversation (prioritized in output)
        max_depth: Maximum directory depth to traverse (default: None for unlimited).
                   Example: max_depth=3 traverses up to 3 levels deep from repository root.

    Returns:
        Formatted repository map with file structures

    Examples:
        >>> get_repo_map(max_files=50)
        Repository Map (50 files):

        src/auth.py:
          Line   45: def login(username: str, password: str) -> bool
          Line   67: def logout(session_id: str) -> None
          Line   89: class AuthManager:

        src/database.py:
          Line   23: class Database:
          Line   45:   def connect(self) -> None
          ...

    Token Efficiency:
        - Traditional approach: Read 50 files × 2,000 tokens = 100,000 tokens
        - With repo map: 50 files × 150 tokens = 7,500 tokens
        - Savings: 92.5%
    """
    _operation_limiter.check_limit(f"get_repo_map(max_files={max_files})")

    # Get supported file extensions
    supported_extensions = set(LANGUAGE_MAP.keys())

    # Convert patterns to sets for faster lookup
    focus_set = set(focus_files or [])

    # Collect all code files
    file_structures: Dict[str, str] = {}
    skipped_count = 0

    # Use depth-limited traversal if max_depth is specified
    if max_depth is not None:
        paths_to_check = depth_limited_walk(REPO_ROOT, max_depth)
    else:
        paths_to_check = REPO_ROOT.rglob("*")

    for path in paths_to_check:
        # Skip directories, hidden files, and non-code files
        if not path.is_file():
            continue
        if any(part.startswith(".") for part in path.parts):
            continue

        ext = path.suffix.lstrip(".")
        if ext not in supported_extensions:
            continue

        # Get relative path
        try:
            rel_path = path.relative_to(REPO_ROOT)
        except ValueError:
            continue

        # Apply include/exclude patterns
        if include_patterns:
            if not any(rel_path.match(pattern) for pattern in include_patterns):
                skipped_count += 1
                continue
        if exclude_patterns:
            if any(rel_path.match(pattern) for pattern in exclude_patterns):
                skipped_count += 1
                continue

        # Try to get from cache
        structure = _REPO_MAP_CACHE.get(path)

        if structure is None:
            # Generate structure
            # Pass _internal_call=True so code_structure doesn't count as an operation
            # This prevents repo_map from using thousands of operations in large repos
            try:
                structure = code_structure(str(rel_path), max_symbols=20, _internal_call=True)
                if structure and not structure.startswith("❌"):
                    # Extract just the essential parts (remove hints and verbose info)
                    lines = structure.split("\n")
                    essential_lines = []
                    for line in lines:
                        # Skip hint lines, empty lines, and file header
                        if line.startswith("💡") or line.startswith("File:"):
                            continue
                        if line.strip():
                            essential_lines.append(line)

                    # Limit to 30 lines per file to keep it compact
                    structure = "\n".join(essential_lines[:30])
                    _REPO_MAP_CACHE.set(path, structure)
                else:
                    structure = None
            except Exception:
                structure = None

        if structure:
            file_structures[str(rel_path)] = structure

    # Mark that we've completed a scan
    _REPO_MAP_CACHE.mark_scanned()

    # Rank files (focus files first, then alphabetically)
    def rank_file(path: str) -> Tuple[int, str]:
        # Priority 0 = focus files, 1 = normal files
        priority = 0 if path in focus_set else 1
        return (priority, path)

    ranked_files = sorted(file_structures.keys(), key=rank_file)

    # Build output (limit to max_files)
    total_files = len(ranked_files)
    showing_files = min(max_files, total_files)

    output_lines = [f"Repository Map ({total_files} files analyzed, showing {showing_files}):\n"]

    if skipped_count > 0:
        output_lines.append(f"(Skipped {skipped_count} files based on include/exclude patterns)\n")

    for file_path in ranked_files[:max_files]:
        structure = file_structures[file_path]
        output_lines.append(f"\n{file_path}:")

        # Show structure (truncate if needed for extremely long files)
        structure_preview = structure[:800]  # ~250 tokens max per file
        if len(structure) > 800:
            structure_preview += "\n  [... more symbols omitted ...]"

        output_lines.append(structure_preview)

    # Add footer with helpful information
    if total_files > max_files:
        output_lines.append(f"\n... and {total_files - max_files} more files not shown")
        output_lines.append(
            "\n💡 Increase max_files parameter or use include_patterns to refine results"
        )

    output_lines.append("\n💡 Use code_structure(path) to see full details for a specific file")
    output_lines.append("💡 Use read_file(path) to see complete implementation")

    result = "\n".join(output_lines)

    # Calculate rough token estimate (1 char ≈ 0.3 tokens for code)
    estimated_tokens = len(result) // 3

    # Log repo map generation
    try:
        from patchpal.tools.audit import log_action_result

        log_action_result(
            tool_name="repo_map_generation",
            description=f"Generated repo map: {len(result):,} chars (~{estimated_tokens:,} tokens) for {total_files} files",
            success=True,
            context={
                "char_count": len(result),
                "estimated_tokens": estimated_tokens,
                "total_files": total_files,
                "focus_files_count": len(focus_set) if focus_set else 0,
                "max_files": max_files,
            },
        )
    except Exception:
        pass  # Don't fail if audit logging fails

    return result


def get_repo_map_stats() -> Dict[str, any]:
    """Get statistics about the repository map cache.

    Returns:
        Dictionary with cache statistics including:
        - cached_files: Number of files in cache
        - last_scan: Timestamp of last full scan
        - cache_age: Seconds since last scan
    """
    return {
        "cached_files": len(_REPO_MAP_CACHE.cache),
        "last_scan": _REPO_MAP_CACHE.last_full_scan,
        "cache_age": time.time() - _REPO_MAP_CACHE.last_full_scan,
    }


def clear_repo_map_cache():
    """Clear the repository map cache.

    Useful if files have been added/removed outside of PatchPal's awareness,
    or if you want to force a fresh scan.
    """
    global _REPO_MAP_CACHE
    _REPO_MAP_CACHE = RepoMapCache()
