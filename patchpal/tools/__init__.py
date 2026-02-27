"""Tools package - Re-exports all tools for backward compatibility.

This package organizes tools into logical modules while maintaining backward
compatibility with the old `from patchpal.tools import func` imports.
"""

# Re-export all tools from their respective modules
from patchpal.config import config  # Export config for direct access
from patchpal.tools.code_analysis import (
    code_structure,
)
from patchpal.tools.common import (
    AUDIT_LOG_FILE,
    BACKUP_DIR,
    # Directories
    PATCHPAL_DIR,
    # Configuration
    REPO_ROOT,
    # Logging
    audit_logger,
    get_operation_count,
    get_require_permission_for_all,
    # Operation counter
    reset_operation_counter,
    # Permission functions
    set_require_permission_for_all,
)
from patchpal.tools.file_reading import (
    read_file,
    read_lines,
)
from patchpal.tools.file_writing import (
    edit_file,
    write_file,
)
from patchpal.tools.repo_map import (
    clear_repo_map_cache,
    get_repo_map,
    get_repo_map_stats,
)
from patchpal.tools.shell_tools import (
    run_shell,
)
from patchpal.tools.todo_tools import (
    reset_session_todos,
    todo_add,
    todo_clear,
    todo_complete,
    todo_list,
    todo_remove,
    todo_update,
)
from patchpal.tools.user_interaction import (
    ask_user,
    list_skills,
    use_skill,
)
from patchpal.tools.web_tools import (
    web_fetch,
    web_search,
)

__all__ = [
    # File operations
    "read_file",
    "read_lines",
    # Code analysis
    "code_structure",
    # Repository map
    "get_repo_map",
    "get_repo_map_stats",
    "clear_repo_map_cache",
    # File editing
    "write_file",
    "edit_file",
    # TODO tools
    "reset_session_todos",
    "todo_add",
    "todo_list",
    "todo_complete",
    "todo_update",
    "todo_remove",
    "todo_clear",
    # Web tools
    "web_fetch",
    "web_search",
    # Shell tools
    "run_shell",
    # User interaction
    "ask_user",
    "list_skills",
    "use_skill",
    # Configuration (use config.PROPERTY instead of static variables)
    "config",
    "REPO_ROOT",
    # Directories
    "PATCHPAL_DIR",
    "BACKUP_DIR",
    "AUDIT_LOG_FILE",
    # Logging
    "audit_logger",
    # Permission functions
    "set_require_permission_for_all",
    "get_require_permission_for_all",
    # Operation counter
    "reset_operation_counter",
    "get_operation_count",
]
