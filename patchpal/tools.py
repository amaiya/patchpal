from pathlib import Path
import subprocess
import difflib

REPO_ROOT = Path(".").resolve()
FORBIDDEN = {"rm", "mv", "sudo", "chmod", "chown", "dd", "curl", "wget"}

def _check_path(path: str, must_exist: bool = True) -> Path:
    """Validate and resolve a path within the repository."""
    p = (REPO_ROOT / path).resolve()
    if not str(p).startswith(str(REPO_ROOT)):
        raise ValueError(f"Path outside repository: {path}")
    if must_exist and not p.is_file():
        raise ValueError(f"File not found: {path}")
    return p

def read_file(path: str) -> str:
    """
    Read the contents of a file in the repository.

    Args:
        path: Relative path to the file from the repository root

    Returns:
        The file contents as a string
    """
    return _check_path(path).read_text()

def list_files() -> list[str]:
    """
    List all files in the repository.

    Returns:
        A list of relative file paths
    """
    return [
        str(p.relative_to(REPO_ROOT))
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and not any(part.startswith('.') for part in p.parts)
    ]

def apply_patch(path: str, new_content: str) -> str:
    """
    Apply changes to a file by replacing its contents.

    Args:
        path: Relative path to the file from the repository root
        new_content: The new complete content for the file

    Returns:
        A confirmation message with the unified diff
    """
    p = _check_path(path, must_exist=False)

    # Read old content if file exists
    if p.exists():
        old = p.read_text().splitlines(keepends=True)
    else:
        old = []

    new = new_content.splitlines(keepends=True)

    # Generate diff
    diff = difflib.unified_diff(
        old,
        new,
        fromfile=f"{path} (before)",
        tofile=f"{path} (after)",
    )
    diff_str = "".join(diff)

    # Write the new content
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(new_content)

    return f"Successfully updated {path}\n\nDiff:\n{diff_str}"

def run_shell(cmd: str) -> str:
    """
    Run a safe shell command in the repository.

    Args:
        cmd: The shell command to execute

    Returns:
        Combined stdout and stderr output
    """
    if any(tok in FORBIDDEN for tok in cmd.split()):
        raise ValueError(f"Blocked command: {cmd}")

    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return result.stdout + result.stderr
