"""List files tool for directory navigation.

This tool provides fast file listing without requiring run_shell access
or expensive code parsing. Useful for read-only agents that need to explore
the repository structure.
"""

from pathlib import Path

from patchpal.tools.common import (
    REPO_ROOT,
    _operation_limiter,
    audit_logger,
    require_permission_for_read,
)


@require_permission_for_read(
    "list_files",
    get_description=lambda path=None, include_hidden=False: (
        f"   List files in {path if path else 'repository'}"
    ),
    get_pattern=lambda path=None, include_hidden=False: path,
)
def list_files(path: str = None, include_hidden: bool = False) -> str:
    """List all files in the repository or a specific directory.

    This tool provides fast file listing without shell access or code parsing.
    Useful for read-only agents that need to explore repository structure.

    Args:
        path: Optional directory path to list (relative to repo root or absolute).
              Defaults to repository root.
        include_hidden: Whether to include hidden files/directories (default: False)

    Returns:
        Newline-separated list of relative file paths
    """
    _operation_limiter.check_limit(f"list_files({path or '.'})")

    # Determine target directory
    if path:
        import os

        expanded_path = os.path.expanduser(path)
        path_obj = Path(expanded_path)
        if path_obj.is_absolute():
            target_dir = path_obj.resolve()
        else:
            target_dir = (REPO_ROOT / expanded_path).resolve()

        if not target_dir.exists():
            raise ValueError(f"Path not found: {path}")

        if not target_dir.is_dir():
            raise ValueError(f"Path is not a directory: {path}")
    else:
        target_dir = REPO_ROOT

    # Collect files
    files = []
    for p in target_dir.rglob("*"):
        if not p.is_file():
            continue

        # Skip hidden files unless requested
        if not include_hidden and any(part.startswith(".") for part in p.parts):
            continue

        try:
            relative_path = p.relative_to(REPO_ROOT)
            files.append(str(relative_path))
        except ValueError:
            # File is outside repo root (if path was absolute)
            files.append(str(p))

    files.sort()

    audit_logger.info(f"LIST_FILES: Found {len(files)} files in {path or 'repository'}")

    if not files:
        return f"No files found in {path or 'repository'}"

    return "\n".join(files)
