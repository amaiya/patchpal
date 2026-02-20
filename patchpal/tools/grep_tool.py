"""Grep search tool for finding patterns in code."""

import shutil
import subprocess
from typing import Optional

from patchpal.tools import common
from patchpal.tools.common import (
    _operation_limiter,
    audit_logger,
    require_permission_for_read,
)


@require_permission_for_read(
    "grep",
    get_description=lambda pattern,
    file_glob=None,
    case_sensitive=True,
    max_results=100,
    path=None: f"   Search code: {pattern}" + (f" in {path}" if path else ""),
    get_pattern=lambda pattern,
    file_glob=None,
    case_sensitive=True,
    max_results=100,
    path=None: path,
)
def grep(
    pattern: str,
    file_glob: Optional[str] = None,
    case_sensitive: bool = True,
    max_results: int = 100,
    path: Optional[str] = None,
) -> str:
    """
    Search for a pattern in files using grep.

    Args:
        pattern: Regular expression pattern to search for
        file_glob: Optional glob pattern to filter files (e.g., "*.py", "src/**/*.js")
        case_sensitive: Whether the search should be case-sensitive (default: True)
        max_results: Maximum number of results to return (default: 100)
        path: Optional file or directory path to search in (relative to repo root or absolute). Defaults to repository root.

    Returns:
        Search results in format "file:line:content" or a message if no results found

    Raises:
        ValueError: If pattern is invalid or search fails
    """
    _operation_limiter.check_limit(f"grep({pattern[:30]}...)")

    # Determine search target (file or directory)
    search_file = None  # If set, search only this specific file
    if path:
        # Expand ~ for home directory and resolve path
        import os
        from pathlib import Path

        expanded_path = os.path.expanduser(path)
        path_obj = Path(expanded_path)
        if path_obj.is_absolute():
            resolved_path = path_obj.resolve()
        else:
            resolved_path = (common.REPO_ROOT / expanded_path).resolve()

        # Validate that the path exists
        if not resolved_path.exists():
            raise ValueError(f"Path not found: {path}")

        # Handle both files and directories
        if resolved_path.is_file():
            # If path points to a file, search just that file
            if file_glob:
                # User specified both path (file) and file_glob - this is ambiguous
                raise ValueError(
                    f"Cannot specify both a file path ({path}) and file_glob ({file_glob}). "
                    f"Use path for a specific file, or use a directory path with file_glob."
                )
            search_file = resolved_path
            search_dir = resolved_path.parent  # For working directory
        elif resolved_path.is_dir():
            # Directory - search recursively within it
            search_dir = resolved_path
        else:
            raise ValueError(f"Path is neither a file nor a directory: {path}")
    else:
        # Default to repository root
        search_dir = common.REPO_ROOT

    # Try ripgrep first (faster), fall back to grep
    use_rg = shutil.which("rg") is not None

    try:
        if use_rg:
            # Build ripgrep command
            cmd = [
                "rg",
                "--no-heading",  # Don't group by file
                "--line-number",  # Show line numbers
                "--color",
                "never",  # No color codes
                "--max-count",
                str(max_results),  # Limit results per file
            ]

            if not case_sensitive:
                cmd.append("--ignore-case")

            # Add glob pattern if searching directory
            if file_glob and not search_file:
                cmd.extend(["--glob", file_glob])

            # Add the search pattern
            cmd.append(pattern)

            # Add specific file if provided
            if search_file:
                cmd.append(str(search_file))

        else:
            # Fall back to grep
            if search_file:
                # Search specific file
                cmd = [
                    "grep",
                    "--line-number",
                    "--binary-files=without-match",  # Skip binary files
                ]

                if not case_sensitive:
                    cmd.append("--ignore-case")

                # Add pattern
                cmd.extend(["--regexp", pattern])

                # Add the specific file
                cmd.append(str(search_file))
            else:
                # Search directory recursively
                cmd = [
                    "grep",
                    "--recursive",
                    "--line-number",
                    "--binary-files=without-match",  # Skip binary files
                ]

                if not case_sensitive:
                    cmd.append("--ignore-case")

                # Add pattern
                cmd.extend(["--regexp", pattern])

                # Add file glob if provided (grep uses --include)
                if file_glob:
                    cmd.extend(["--include", file_glob])

                # Current directory
                cmd.append(".")

        # Execute search from specified directory
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, cwd=search_dir)

        # ripgrep/grep return exit code 1 when no matches found (not an error)
        # exit code 0 = matches found
        # exit code 1 = no matches
        # exit code 2+ = actual error

        if result.returncode > 1:
            # Actual error occurred
            raise ValueError(f"Search failed: {result.stderr or 'Unknown error'}")

        # Process output
        output = result.stdout.strip()

        search_location = f" in {path}" if path else ""
        if not output or result.returncode == 1:
            audit_logger.info(f"GREP: {pattern}{search_location} - No matches found")
            return f"No matches found for pattern: {pattern}{search_location}"

        # Count and limit results
        lines = output.split("\n")
        total_matches = len(lines)

        if total_matches > max_results:
            lines = lines[:max_results]
            output = "\n".join(lines)
            output += f"\n\n... (showing first {max_results} of {total_matches} matches)"

        audit_logger.info(f"GREP: {pattern}{search_location} - Found {total_matches} matches")
        return output

    except subprocess.TimeoutExpired:
        raise ValueError(
            "Search timed out after 30 seconds\n"
            "Try narrowing your search with a file_glob parameter"
        )
    except ValueError:
        # Re-raise ValueError (from our checks above)
        raise
    except Exception as e:
        raise ValueError(f"Search error: {e}")
