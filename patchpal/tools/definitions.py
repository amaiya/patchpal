"""Tool definitions for PatchPal agent.

This module contains the tool schemas (in LiteLLM format) and the mapping
from tool names to their implementation functions.
"""

import os

from patchpal.config import config
from patchpal.tools import (
    apply_patch,
    ask_user,
    code_structure,
    edit_file,
    edit_file_hashline,
    get_repo_map,
    list_skills,
    read_file,
    read_lines,
    run_shell,
    todo_add,
    todo_clear,
    todo_complete,
    todo_list,
    todo_remove,
    todo_update,
    use_skill,
    web_fetch,
    web_search,
)
from patchpal.tools.mcp import load_mcp_tools

# Define tools in LiteLLM format
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file. Can read files anywhere on the system (repository files, system configs like /etc/fstab, logs, etc.) for automation and debugging. Supports text files, images (PNG, JPG, GIF, etc.), and documents (PDF, DOCX, PPTX) with automatic format detection. Images are returned as base64 data URLs for vision model analysis. Sensitive files (.env, credentials) are blocked for safety.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path (e.g., /etc/fstab, /var/log/app.log)",
                    }
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_lines",
            "description": "Read specific lines from a file without loading the entire file. Useful for viewing code sections, error context, or specific regions of large files. More efficient than read_file when you only need a few lines.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - can be relative to repository root or an absolute path",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Starting line number (1-indexed)",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "Ending line number (inclusive, 1-indexed). If omitted, reads only start_line",
                    },
                },
                "required": ["path", "start_line"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "code_structure",
            "description": "Analyze code structure using tree-sitter AST parsing without reading the full file. Returns a compact overview showing functions, classes, methods with their line numbers and signatures. Supports 40+ languages including Python, JavaScript, TypeScript, Go, Rust, Java, C/C++. Use this INSTEAD OF read_file when you need structure overview but not implementation details (e.g., finding function names, understanding file organization). For exploring multiple files or getting oriented in a codebase, use get_repo_map instead—it's much more efficient than calling code_structure on each file individually.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the code file to analyze - can be relative to repository root or absolute path",
                    },
                    "max_symbols": {
                        "type": "integer",
                        "description": "Maximum number of symbols (functions/classes) to show (default: 50)",
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_repo_map",
            "description": """Generate a repository map showing code structure across the entire codebase.

This provides a consolidated view of ALL files in the repository, showing function and class
signatures without implementations. More efficient than calling code_structure on each file individually.

Use this when you need to:
- Understand the overall codebase structure
- Find relevant files without analyzing them all
- Discover related code across the project
- Get oriented in an unfamiliar codebase

Supports 20+ languages: Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, C#, Ruby,
PHP, Swift, Kotlin, Scala, Elm, Elixir, and more. Language detection is automatic.

Token efficiency: 38-70% reduction compared to calling code_structure on each file
(e.g., 20 files: 4,916 tokens vs 1,459 tokens = 70% savings; 37 files: 8,052 tokens vs 4,988 tokens = 38% savings)
Combines multiple file structures into one compact output with reduced redundant formatting.

Tip: Read README first for context when exploring repositories.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_files": {
                        "type": "integer",
                        "description": "Maximum number of files to include in the map (default: 100)",
                    },
                    "include_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to include (e.g., ['*.py', 'src/**/*.js']). If specified, only matching files are included.",
                    },
                    "exclude_patterns": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Glob patterns to exclude (e.g., ['*test*', '*_pb2.py', 'vendor/**']). Useful for filtering out generated code, tests, or dependencies.",
                    },
                    "focus_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Files to prioritize in the output (e.g., files mentioned in conversation). These appear first in the map.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit a file by replacing an exact string. More efficient than apply_patch for small changes. The old_string must match exactly and appear only once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path",
                    },
                    "old_string": {
                        "type": "string",
                        "description": "The exact string to find and replace (must match exactly including all whitespace; use read_lines to get exact text, or use apply_patch for complex changes)",
                    },
                    "new_string": {
                        "type": "string",
                        "description": "The string to replace it with",
                    },
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file_hashline",
            "description": """Edit a file using hashline-based line references for precise, stable edits. Uses content hashes to verify line identity, preventing edits from being applied to the wrong location if the file changed.

Each line is identified as 'LINE#HASH' (e.g., '5#ZP'). When reading files, you'll see lines formatted as 'LINE#HASH:content'.

Supported operations:
- set: Replace a single line
- replace: Replace a range of lines
- append: Append lines after a specific line (or at EOF if no 'after')
- prepend: Prepend lines before a specific line (or at BOF if no 'before')
- insert: Insert lines between two specific lines

Example: {"op": "set", "tag": "5#ZP", "content": ["new line"]}

If you get a HashlineMismatchError, use the corrected LINE#ID references shown in the error message.""",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path",
                    },
                    "edits": {
                        "type": "array",
                        "description": "Array of edit operations to apply",
                        "items": {
                            "type": "object",
                            "properties": {
                                "op": {
                                    "type": "string",
                                    "enum": ["set", "replace", "append", "prepend", "insert"],
                                    "description": "Operation type",
                                },
                                "tag": {
                                    "type": "string",
                                    "description": "Line reference (LINE#HASH) for set operation",
                                },
                                "first": {
                                    "type": "string",
                                    "description": "First line reference (LINE#HASH) for replace operation",
                                },
                                "last": {
                                    "type": "string",
                                    "description": "Last line reference (LINE#HASH) for replace operation",
                                },
                                "after": {
                                    "type": "string",
                                    "description": "Line reference (LINE#HASH) to append/insert after",
                                },
                                "before": {
                                    "type": "string",
                                    "description": "Line reference (LINE#HASH) to prepend/insert before",
                                },
                                "content": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "Array of new lines to insert/replace (can also be a single string)",
                                },
                            },
                            "required": ["op", "content"],
                        },
                    },
                },
                "required": ["path", "edits"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apply_patch",
            "description": "Replace a file's entire contents with new content. You MUST provide the complete new file content as a string. Prefer edit_file for targeted changes. Use this for large-scale rewrites or creating new files. Returns a unified diff of changes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the file - relative to repository root or absolute path",
                    },
                    "new_content": {
                        "type": "string",
                        "description": "The complete new file content (you must provide the entire file contents, not just changes)",
                    },
                },
                "required": ["path", "new_content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for information. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results to return (default: 5, max: 10)",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_fetch",
            "description": "Fetch and read content from a URL. Supports text extraction from HTML, PDF, DOCX (Word), PPTX (PowerPoint), and plain text files. Requires permission to prevent information leakage about your codebase.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch (must start with http:// or https://)",
                    },
                    "extract_text": {
                        "type": "boolean",
                        "description": "If true, extract readable text from HTML/PDF/DOCX/PPTX (default: true)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_skills",
            "description": "List all available skills. When telling users about skills, instruct them to use /skillname syntax (e.g., /commit).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "use_skill",
            "description": "Invoke a skill programmatically when it's relevant to the user's request. Note: Users invoke skills via /skillname at the CLI, not by calling tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Name of the skill to invoke (without / prefix)",
                    },
                    "args": {
                        "type": "string",
                        "description": "Optional arguments to pass to the skill",
                    },
                },
                "required": ["skill_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_add",
            "description": "Add a new task to the TODO list. Use this to break down complex tasks into manageable subtasks. Essential for planning multi-step work.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Brief task description (one line)",
                    },
                    "details": {
                        "type": "string",
                        "description": "Optional detailed notes about the task",
                    },
                },
                "required": ["description"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_list",
            "description": "List all tasks in the TODO list with their status and progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_completed": {
                        "type": "boolean",
                        "description": "If true, show completed tasks; if false, show only pending tasks (default: false)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_complete",
            "description": "Mark a task as completed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to complete",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_update",
            "description": "Update a task's description or details.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to update",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description (optional)",
                    },
                    "details": {
                        "type": "string",
                        "description": "New details (optional)",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_remove",
            "description": "Remove a task from the TODO list.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to remove",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "todo_clear",
            "description": "Clear tasks from the TODO list (completed tasks only by default, or all tasks).",
            "parameters": {
                "type": "object",
                "properties": {
                    "completed_only": {
                        "type": "boolean",
                        "description": "If true, clear only completed tasks; if false, clear all tasks (default: true)",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a question and wait for their response. Use this to clarify requirements, get decisions, or gather additional information during task execution.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The question to ask the user",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of predefined answer choices (e.g., ['yes', 'no', 'skip']). User can select from these or provide custom answer.",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_shell",
            "description": "Run a safe shell command in the repository. Commands execute from repository root automatically (no need for 'cd'). Privilege escalation (sudo, su) and destructive patterns (rm -rf /, piping to dd, writing to /dev/) blocked by default unless PATCHPAL_ALLOW_SUDO=true.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cmd": {"type": "string", "description": "The shell command to execute"}
                },
                "required": ["cmd"],
            },
        },
    },
]

# Map tool names to functions
TOOL_FUNCTIONS = {
    "read_file": read_file,
    "read_lines": read_lines,
    "code_structure": code_structure,
    "get_repo_map": get_repo_map,
    "edit_file": edit_file,
    "edit_file_hashline": edit_file_hashline,
    "apply_patch": apply_patch,
    "web_search": web_search,
    "web_fetch": web_fetch,
    "list_skills": list_skills,
    "use_skill": use_skill,
    "todo_add": todo_add,
    "todo_list": todo_list,
    "todo_complete": todo_complete,
    "todo_update": todo_update,
    "todo_remove": todo_remove,
    "todo_clear": todo_clear,
    "ask_user": ask_user,
    "run_shell": run_shell,
}


def get_tools(web_tools_enabled: bool = True):
    """Get the list of available tools, optionally filtering out web tools.

    Args:
        web_tools_enabled: Whether to include web_search and web_fetch tools

    Returns:
        Tuple of (tools_list, tool_functions_dict)
    """
    # Check if minimal tools mode is enabled (for local models with tool confusion)
    minimal_mode = config.MINIMAL_TOOLS

    if minimal_mode:
        # Base minimal tools (always included)
        minimal_tool_names = ["read_file", "edit_file", "apply_patch", "run_shell"]

        # Add web tools if enabled
        if web_tools_enabled:
            minimal_tool_names.extend(["web_search", "web_fetch"])

        tools = [tool for tool in TOOLS if tool["function"]["name"] in minimal_tool_names]
        functions = {
            name: func for name, func in TOOL_FUNCTIONS.items() if name in minimal_tool_names
        }

        return tools, functions

    # Start with built-in tools
    tools = TOOLS.copy()
    functions = TOOL_FUNCTIONS.copy()

    # Check if hashline mode is enabled - swap edit_file for edit_file_hashline
    hashline_mode = os.getenv("PATCHPAL_HASHLINE", "false").lower() in ("true", "1", "yes")
    if hashline_mode:
        # Remove edit_file and keep edit_file_hashline
        tools = [tool for tool in tools if tool["function"]["name"] != "edit_file"]
        if "edit_file" in functions:
            del functions["edit_file"]
    else:
        # Remove edit_file_hashline and keep edit_file
        tools = [tool for tool in tools if tool["function"]["name"] != "edit_file_hashline"]
        if "edit_file_hashline" in functions:
            del functions["edit_file_hashline"]

    # Filter out web tools if disabled
    if not web_tools_enabled:
        tools = [
            tool for tool in tools if tool["function"]["name"] not in ("web_search", "web_fetch")
        ]
        functions = {k: v for k, v in functions.items() if k not in ("web_search", "web_fetch")}

    # Load MCP tools dynamically (unless disabled via environment variable)
    if config.ENABLE_MCP:
        try:
            mcp_tools, mcp_functions = load_mcp_tools()
            if mcp_tools:
                tools.extend(mcp_tools)
                functions.update(mcp_functions)
        except Exception as e:
            # Graceful degradation - MCP tools are optional
            print(f"Warning: Failed to load MCP tools: {e}")

    return tools, functions
