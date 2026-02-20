# Built-In Tools

PatchPal provides 20 built-in tools for file operations, code analysis, web access, task planning, and user interaction.

## File Operations (3 tools)

### read_file
Read contents of files anywhere on the system (repository files, logs, configs).

- **Example**: `read_file("src/app.py")`
- Supports PDF, DOCX, PPTX text extraction
- Limited to 500KB by default (configurable with `PATCHPAL_MAX_FILE_SIZE`)
- For larger files, use `read_lines` for targeted access

### read_lines
Read specific line ranges from a file without loading the entire file.

- **Example**: `read_lines("app.py", 100, 150)` - read lines 100-150
- More efficient than `read_file` when you only need a few lines
- Useful for viewing code sections, error context, or specific regions

### get_file_info
Get detailed metadata for file(s) - size, modification time, type.

- **Single file**: `get_file_info("file.txt")`
- **Directory**: `get_file_info("src/")`
- **Glob patterns**: `get_file_info("tests/*.py")`

## Code Analysis (2 tools)

### code_structure
Analyze code structure using tree-sitter AST parsing without reading full files.

- **Example**: `code_structure("app.py")` - see all classes, functions, methods with line numbers
- **95% token savings** vs `read_file` for large code files
- Supports **40+ languages**: Python, JavaScript, TypeScript, Go, Rust, Java, C/C++, Ruby, PHP, and more
- Shows function signatures and line numbers for easy navigation
- **Best practice**: Use with `read_lines` - analyze structure first, then read specific sections

### get_repo_map
Get an overview of the entire codebase in one call.

- **Example**: `get_repo_map(max_files=100)` - see structure of up to 100 files at once
- Shows function/class signatures from ALL files in a consolidated view
- **Filtering**: `get_repo_map(include_patterns=["*.py"], exclude_patterns=["*test*"])`
- **38-70% token savings** vs calling `code_structure` on each file individually
- Ideal for understanding codebase structure and finding relevant files

## File Editing (2 tools)

### edit_file
Edit a file by replacing an exact string (efficient for small changes).

- **Example**: `edit_file("config.py", "port = 3000", "port = 8080")`
- More efficient than `apply_patch` for targeted changes
- Old string must appear exactly once in the file
- Best for single-line or small multi-line edits

### apply_patch
Modify files by replacing entire contents.

- **Example**: `apply_patch("config.py", new_content)`
- Use for large-scale changes or multiple edits
- Returns unified diff showing changes
- Best for rewriting entire files or complex modifications

## Search (1 tool)

### grep
Search for patterns in code files with regex support.

- **Example**: `grep("TODO", file_glob="*.py")` - find all TODOs in Python files
- **Example**: `grep("function.*userId", path="src/")` - regex search in src directory
- Uses ripgrep (if available) or falls back to grep
- Much faster than `run_shell` with grep
- Returns results in `file:line:content` format
- Supports case-insensitive search, file filtering, result limits

## Web Tools (2 tools)

⚠️ **Requires permission** to prevent information leakage about your codebase.

### web_search
Search the web using DuckDuckGo (no API key required).

- **Example**: `web_search("Python asyncio best practices")`
- Look up error messages and solutions
- Find current documentation and best practices
- Research library versions and compatibility
- Returns top search results with titles, snippets, and URLs

### web_fetch
Fetch and read content from URLs.

- **Example**: `web_fetch("https://docs.python.org/3/library/asyncio.html")`
- Read documentation pages and API references
- Extract text from HTML, PDF, DOCX (Word), and PPTX (PowerPoint)
- Supports plain text, JSON, XML, and other text formats
- Warns about unsupported binary formats (images, videos, archives)

## Task Planning (6 tools)

### todo_add
Add a new task to break down complex work into manageable subtasks.

- **Example**: `todo_add("Implement authentication", details="Use JWT tokens")`
- Each task gets a unique ID for tracking
- Use for multi-step workflows

### todo_list
Show all tasks with their status and progress.

- **Example**: `todo_list()` - show pending tasks only
- **Example**: `todo_list(show_completed=True)` - show all tasks including completed

### todo_complete
Mark a task as done.

- **Example**: `todo_complete(1)` - mark task #1 as completed

### todo_update
Update task description or details.

- **Example**: `todo_update(1, description="Implement OAuth2 authentication")`

### todo_remove
Remove a task from the list.

- **Example**: `todo_remove(1)` - remove task #1

### todo_clear
Clear completed tasks or start fresh.

- **Example**: `todo_clear()` - clear completed tasks only
- **Example**: `todo_clear(completed_only=False)` - clear all tasks

## Skills (2 tools)

### list_skills
List all available skills (e.g., /commit, /test, /debug).

- Skills are higher-level commands that combine multiple tools
- Users invoke skills with `/skillname` syntax at the CLI

### use_skill
Invoke a skill programmatically when relevant to the request.

- **Example**: `use_skill("commit", args="Fix authentication bug")`
- Note: Users invoke skills via `/skillname` at CLI, not by calling this tool

## User Interaction (1 tool)

### ask_user
Ask the user a question during task execution.

- **Example**: `ask_user("Which database should I use?", options=["PostgreSQL", "MySQL", "SQLite"])`
- Useful for clarifying requirements, getting decisions, or gathering additional information
- Supports multiple choice options or free-form answers

## Shell (1 tool)

### run_shell
Execute shell commands in the repository.

- **Example**: `run_shell("pytest tests/test_auth.py")`
- **Example**: `run_shell("npm install lodash")`
- Commands execute from repository root automatically (no need for `cd`)
- **56 harmless commands auto-granted** (no permission prompts):
  - File operations: `wc`, `stat`, `find`, `ls`, `cat`, `head`, `tail`
  - Search: `grep`, `awk`
  - Git (read-only): `git status`, `git diff`, `git log`
  - System info: `whoami`, `hostname`, `date`, `uname`
  - Network diagnostics: `ping`, `tracert`, `nslookup`
- Dangerous commands require permission (e.g., `rm`, `pip install`, script execution)
- Privilege escalation blocked by default (set `PATCHPAL_ALLOW_SUDO=true` to enable)

## Tool Count by Category

| Category | Tools | Count |
|----------|-------|-------|
| File Operations | read_file, read_lines, get_file_info | 3 |
| Code Analysis | code_structure, get_repo_map | 2 |
| File Editing | edit_file, apply_patch | 2 |
| Search | grep | 1 |
| Web | web_search, web_fetch | 2 |
| Task Planning | todo_add, todo_list, todo_complete, todo_update, todo_remove, todo_clear | 6 |
| Skills | list_skills, use_skill | 2 |
| User Interaction | ask_user | 1 |
| Shell | run_shell | 1 |
| **Total** | | **20** |

## Configuration

### Environment Variables

- `PATCHPAL_MAX_FILE_SIZE` - Maximum file size for read_file (default: 500KB)
- `PATCHPAL_ENABLE_WEB` - Enable/disable web tools (default: true)
- `PATCHPAL_ALLOW_SUDO` - Allow sudo/su commands (default: false)
- `PATCHPAL_MINIMAL_TOOLS` - Use minimal tools mode: 4-6 core tools only (default: false)

### Minimal Tools Mode

When `PATCHPAL_MINIMAL_TOOLS=true`, only these tools are available:
- `read_file`, `edit_file`, `apply_patch`, `run_shell`
- `web_search`, `web_fetch` (if `PATCHPAL_ENABLE_WEB=true`)

This reduces tool count to 4-6 for local models with tool confusion issues. Harmless shell commands still work without permission prompts.

## Permission System

### Read Operations (Auto-Granted)
- Reading repository files
- Listing files and directories
- Searching with grep
- Analyzing code structure
- Git read-only operations (status, diff, log)
- System information commands

### Write Operations (Require Permission)
- Editing/patching files outside repository
- Dangerous shell commands
- Web access (to prevent info leakage)
- Installation commands (pip, npm, etc.)

### Bypass Permission Prompts
Set `PATCHPAL_REQUIRE_PERMISSION=false` to auto-grant all operations (use carefully).
