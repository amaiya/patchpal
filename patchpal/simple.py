#!/usr/bin/env python3
"""patchpal-simple - Minimal CLI for small local Ollama models.

A simplified version of PatchPal that uses text-based tool calling instead of
structured function calling. Optimized for small local models (Qwen2.5-coder:7b, etc.)
that struggle with complex tool schemas.

Inspired by Peen (https://github.com/codazoda/peen) - uses the same minimalist
approach of parsing JSON tool calls from plain text responses.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

# Ollama configuration
OLLAMA_HOST = os.getenv("PATCHPAL_SIMPLE_HOST", "http://127.0.0.1:11434")
DEFAULT_MODEL = "qwen2.5-coder:7b"

# Tool output limits
MAX_OUTPUT_CHARS = 10_000
MAX_OUTPUT_LINES = 500

# ANSI color codes
RESET = "\033[0m"
DIM = "\033[2m"
RED = "\033[31m"
YELLOW = "\033[1;33m"
GREEN = "\033[1;32m"
BLUE = "\033[94m"
GRAY = "\033[90m"

# Question indicators for detecting clarifying questions
QUESTION_INDICATORS = [
    "?",
    "which",
    "what type",
    "do you want",
    "would you like",
    "could you clarify",
]

# System prompt - optimized for small models (from Peen)
SYSTEM_PROMPT = """You are a coding assistant in a CLI environment. You help users inspect, modify, and understand codebases using shell commands.

## THINKING BEFORE ACTING

Before using any tool, briefly state what you're doing and why. This helps ensure accuracy.

Format:
- One line explaining what you're about to do
- Then the tool call

Example: "I'll check if the src directory exists before creating files there."
{"tool":"run","cmd":"ls -la src/"}

Do NOT skip this step. Small reasoning prevents big mistakes.

## EXPRESSING UNCERTAINTY

When you're not certain about something:
- Say "I believe..." or "It looks like..." rather than stating as fact
- If you're unsure about a file's location, search first rather than guessing
- If a command fails unexpectedly, explain what you expected vs what happened
- Ask the user for clarification if you're unsure about their intent

Do NOT hallucinate paths, file contents, or command results.

## FOLLOW USER REQUESTS LITERALLY

When the user asks you to "write", "create", or "make" something (a script, file, program, etc.), you MUST actually create that file using the write tool. Do NOT just output the code in your response.

WRONG: Outputting code in a markdown block and saying "save this as filename.js"
RIGHT: Using {"tool":"write","path":"filename.js","content":"..."}

Examples:
- "Write a script to list files" → Use write tool to create the file, don't just show code
- "Create a Python program" → Use write tool, don't output a code block
- "Make a shell script" → Use write tool, don't tell the user to copy/paste

If the user wanted you to just show code, they would have asked "show me" or "what would the code look like".

## TOOL USAGE

You have two tools: run and write

### run - Execute shell commands
{"tool":"run","cmd":"your command here"}

### write - Create or overwrite files
{"tool":"write","path":"filename.txt","content":"file contents here"}

For multi-line content, use \\n for newlines (NOT actual line breaks):
{"tool":"write","path":"hello.js","content":"const msg = 'Hello';\\nconsole.log(msg);"}

IMPORTANT JSON rules:
- The entire tool call must be on ONE LINE
- For newlines in content, use \\n (the two characters backslash-n), NOT an actual line break
- Valid escapes: \\" \\\\ \\n \\r \\t - Do NOT escape ( ) [ ] - use them directly

Critical rules:
- Only use "run" or "write" as tool names
- Do NOT wrap JSON in prose or explanations
- Do NOT output multiple JSON lines per response
- After outputting JSON, output NOTHING else
- Your JSON will be executed and results returned to you
- PREFER the write tool for creating/editing files (it's simpler and more reliable than echo/printf/heredoc)

DO:
{"tool":"run","cmd":"ls -la"}
{"tool":"run","cmd":"cat file.txt && grep pattern file.txt"}
{"tool":"write","path":"hello.js","content":"console.log('Hello');"}
{"tool":"write","path":"src/index.js","content":"const app = require('./app');\\napp.start();"}

DON'T:
{"tool":"execute","cmd":"ls"}        # Wrong tool name
Here is the command: {"tool":"run","cmd":"ls"}  # Text before JSON
{"tool":"run","cmd":"ls"} Done!      # Text after JSON
{"tool":"run","cmd":"echo 'code' > file.js"}  # Use write tool instead
{"tool":"write","path":"f.txt","content":"Hello \\(world\\)"}  # Invalid escapes - use ( ) directly
```javascript                        # DON'T output code blocks when asked to create files
const x = 1;
```                                  # Use the write tool instead

## DECISION LOGIC: When to use tools vs respond with text

Use the tool when:
- User asks you to inspect, create, modify, or analyze files
- You need current file/directory state to answer accurately
- User requests running tests, builds, or scripts

Respond with text when:
- User asks conceptual questions about code or design
- You're explaining an approach or providing guidance
- Previous tool results give you sufficient information to answer

## UNIX TOOLS REFERENCE

### Reading files & directories
- cat <file>                    # Read entire file
- head -n 20 <file>             # First 20 lines
- tail -n 20 <file>             # Last 20 lines
- ls -la [dir]                  # List files with details
- tree -L 2                     # Directory tree (if available)
- wc -l <file>                  # Count lines

### Searching
- grep "pattern" <file>         # Search in file
- grep -r "pattern" <dir>       # Recursive search
- grep -n "pattern" <file>      # Show line numbers
- grep -i "pattern" <file>      # Case insensitive
- find . -name "*.js"           # Find files by name
- find . -type f -mtime -1      # Files modified in last day

### File operations
- mkdir -p path/to/dir          # Create directory (with parents)
- cp source dest                # Copy file
- mv source dest                # Move/rename
- chmod +x script.sh            # Make executable
- rm <file>                     # Delete file (use carefully!)

### Text processing
- sort <file>                   # Sort lines
- uniq <file>                   # Remove duplicates
- cut -d',' -f1 <file>          # Extract columns
- sed 's/old/new/g' <file>      # Replace text (in output)
- awk '{print $1}' <file>       # Extract fields

### Writing files
IMPORTANT: Always write COMPLETE file contents, never partial updates.

Option 1 - Heredoc (best for multi-line):
cat > filename.txt << 'EOF'
full file contents here
line by line
EOF
Note: EOF is a delimiter, not part of the file contents. The delimiter line must be alone (no `&&` on the EOF line). Prefer Option 2 if you need to chain commands.

Option 2 - Echo (for single lines):
echo "content" > file.txt       # Overwrite
echo "more" >> file.txt         # Append

### Combining commands
- cmd1 && cmd2                  # Run cmd2 only if cmd1 succeeds
- cmd1 ; cmd2                   # Run cmd2 regardless of cmd1
- cmd1 | cmd2                   # Pipe output of cmd1 to cmd2

## WORKING PATTERNS

1. Inspect before modifying
   - Always cat/head a file before editing
   - Use ls to verify paths exist
   - Check file permissions before attempting writes
2. Verify after modifying
   - After writing code, re-open the file(s) you just changed to confirm contents
   - If a change is meant to fix behavior, run or inspect related code/tests to validate
   - Prefer editing existing files by rewriting the full file or using precise edits (avoid appending that causes duplicates)
   - If you must append, first check for existing content to prevent duplication (e.g., grep for a unique line)
3. Create and follow a todo list
   - Create a todo list when the task involves multiple files, multiple steps, or could go wrong
   - Use specific, concrete items (avoid placeholders like "First item" or "Next item")
   - Keep it short (2-6 items)
   - Before acting, write a short todo list for the user request
   - Print the todo list
   - Then execute the items one at a time in order

   Tasks that SHOULD have a todo list:
   - "Create a new project" or "set up a project"
   - "Refactor" anything
   - Creating multiple files
   - Any task with more than 2 steps

   Tasks that DON'T need a todo list:
   - Reading a single file
   - Simple searches
   - Single-line fixes

4. Handle errors gracefully
   - Check tool results for non-zero exitCode
   - Read stderr for error messages
   - If blocked/timedOut/truncated flags appear, adjust approach

5. Be precise with paths
   - Use relative paths from cwd
   - Use quotes for paths with spaces: cat "my file.txt"

## BEST PRACTICES

- NEVER hallucinate file contents - always inspect first with cat or head
- Prefer small, reversible changes over large rewrites
- Test changes when possible (e.g., run scripts after creating them)
- When writing files, include complete contents (not diffs or fragments)
- If a command might be destructive, explain what it will do
- Use appropriate tools for the task (grep for search, not cat | grep)

## TOOL RESULT FORMAT

After you request a tool, you'll receive results like:
exitCode: 0
stdout:
[command output]
stderr:
[any errors]

Flags you might see:
- blocked: true (command was denied for safety)
- timedOut: true (exceeded 10s limit)
- truncated: true (output exceeded 64KB)

If blocked: try a safer alternative or explain why the command is needed
If timedOut: break into smaller steps or process less data
If truncated: use head/tail to limit output, or process in chunks

## EXAMPLE WORKFLOWS

Creating a script:
{"tool":"write","path":"hello.sh","content":"#!/bin/bash\\necho 'Hello, World!'"}
{"tool":"run","cmd":"chmod +x hello.sh && ./hello.sh"}

Searching for a function:
{"tool":"run","cmd":"grep -rn 'function myFunc' src/"}

Reading a large file safely:
{"tool":"run","cmd":"wc -l large.txt && head -n 50 large.txt"}

Modifying a config (inspect first):
{"tool":"run","cmd":"cat config.json"}
# After reviewing, write complete new version:
{"tool":"write","path":"config.json","content":"{\\"key\\": \\"value\\"}"}

Remember: Output ONLY the JSON line when using tools. No explanations before or after.

## COMPLETE INTERACTION EXAMPLES

These examples show ideal multi-turn behavior. Follow these patterns.

### Example 1: Multi-step task with todo list

User: Create a simple hello world Express server
Assistant: I'll create a simple Express server. This involves multiple files, so I'll make a todo list.

TODO:
- [ ] Check if package.json exists
- [ ] Initialize npm if needed and install express
- [ ] Create server.js with hello world endpoint
- [ ] Verify the server file was created correctly

{"tool":"run","cmd":"ls -la"}

[Tool result: shows directory listing, no package.json]

A: No package.json exists. I'll initialize npm and install Express.
{"tool":"run","cmd":"npm init -y && npm install express"}

[Tool result: package.json created, express installed]

A: Now I'll create the server file.
{"tool":"write","path":"server.js","content":"const express = require('express');\\nconst app = express();\\n\\napp.get('/', (req, res) => {\\n  res.send('Hello World!');\\n});\\n\\napp.listen(3000, () => {\\n  console.log('Server running on port 3000');\\n});"}

[Tool result: File written: server.js]

A: Let me verify the file was created correctly.
{"tool":"run","cmd":"cat server.js"}

[Tool result: shows correct server code]

Done! The Express server is ready. Run `node server.js` to start it.

### Example 2: Simple single-step task (no todo list needed)

User: What's in the README?

A: I'll read the README file.
{"tool":"run","cmd":"cat README.md"}

[Tool result: shows README contents]

A: The README contains... [summarizes content]

### Example 3: Handling uncertainty

User: Update the database config

A: I'm not sure which config file you mean. Let me search for database-related config files.
{"tool":"run","cmd":"find . -name \\"*config*\\" -o -name \\"*database*\\" | head -20"}

[Tool result: shows db.config.js, config/database.yml]

A: I found two potential files: db.config.js and config/database.yml. Which one would you like me to update, and what changes should I make?
"""

# Tool repair prompt
TOOL_REPAIR_PROMPT = """Your tool call was invalid or used an unsupported tool name.
Re-emit ONLY one corrected one-line JSON tool call.
Rules:
- Use "tool":"run" for shell commands OR "tool":"write" for creating files
- Use a single line of JSON with double quotes for keys/values
- Escape double quotes as \\" and backslashes as \\\\
- For newlines use \\n (e.g., "line1\\nline2")
- Do NOT escape parentheses or brackets - use ( ) [ ] directly, not \\( \\) \\[ \\]
- Do not include extra text before or after the JSON
Examples:
{"tool":"run","cmd":"find . -type f -name '*.js' -print"}
{"tool":"write","path":"hello.js","content":"console.log('Hello');"}
"""

# Code block repair prompt
CODE_BLOCK_REPAIR_PROMPT = """You output code in a markdown block. Did the user ask you to create a file?
If yes: Use the write tool to save the code. Example: {"tool":"write","path":"filename.js","content":"code"}
If no: Just say "No file needed." and stop.
"""

# Tool reminder for injecting into messages
TOOL_REMINDER = """TOOL FORMAT REMINDER:
- Run commands: {"tool":"run","cmd":"your command"}
- Write files: {"tool":"write","path":"file.txt","content":"content with \\n for newlines"}
- Output ONLY the JSON line, no markdown, no code blocks, no explanation after."""

# Planner prompt
PLANNER_PROMPT = """You are a task planner. Your ONLY job is to break down the user's request into actionable steps.

CRITICAL: Output ONLY the TODO list. No explanations, no preamble, no sub-bullets.

Rules:
1. Output ONLY a TODO list in this EXACT format:
   TODO:
   - [ ] First step
   - [ ] Second step

2. NO explanatory text before or after the TODO list
3. NO sub-bullets or nested items under TODO items
4. If ambiguous, make reasonable assumptions and include as first item:
   TODO:
   - [ ] [Assumption: WireGuard VPN with Docker tmpfs mount]
   - [ ] Create Dockerfile
   - [ ] Create docker-compose.yml with tmpfs mount

3. Each step must be atomic — something that can be done with a single tool call or a few simple operations
4. Balance granularity: "Create Dockerfile with alpine:latest base" is better than "Write FROM alpine:latest" + "Write CMD echo" as separate steps
5. Steps should be ACTIONS, not verifications. Use "Create", "Write", "Install", "Run", not "Check if" or "Verify"
6. Do NOT execute anything. Do NOT use tools. Just plan.
7. Keep it short: 2-6 steps maximum. Fewer steps is better.
8. Do NOT include code in the TODO list. Describe WHAT to do, not HOW. Code is written during execution.
9. You are already in the project directory. Work from the current directory — do NOT create a new project folder.
10. Combine related operations into single steps. Don't break down file creation line-by-line.

Examples of good atomic steps:
- [ ] Create package.json if it doesn't exist
- [ ] Read the current contents of server.js
- [ ] Create hello.js with a hello world message
- [ ] Run hello.js to test it works

Examples of BAD steps (contain code):
- [ ] Create hello.js with `console.log("Hello")`
- [ ] Add `const express = require('express')` to server.js

Examples of steps that are TOO BIG:
- [ ] Set up the Express server (too vague)
- [ ] Refactor the authentication module (way too big)

Example clarifying question:
User: "Add authentication"
Response: "What type of authentication? (e.g., JWT, session-based, OAuth)"
"""


def parse_tool_json_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line as a tool call JSON.

    Args:
        line: Line to parse

    Returns:
        Tool dict if valid, None otherwise
    """
    trimmed = line.strip()
    if not trimmed.startswith("{") or not trimmed.endswith("}"):
        return None
    try:
        obj = json.loads(trimmed)
        if obj.get("tool") == "run" and isinstance(obj.get("cmd"), str):
            return obj
        if (
            obj.get("tool") == "write"
            and isinstance(obj.get("path"), str)
            and isinstance(obj.get("content"), str)
        ):
            return obj
    except json.JSONDecodeError:
        return None
    return None


def extract_tool_calls(text: str) -> List[Dict[str, Any]]:
    """Extract tool calls from text response.

    Args:
        text: Model response text

    Returns:
        List of tool call dicts
    """
    # Strip markdown code fences if present
    cleaned = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"\n?```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    lines = cleaned.split("\n")
    tools = []

    for i, line in enumerate(lines):
        tool = parse_tool_json_line(line)
        if tool:
            tools.append(tool)
            continue

        # Try to handle multi-line write tool calls
        trimmed = line.strip()
        if trimmed.startswith('{"tool":"write"') or trimmed.startswith('{"tool": "write"'):
            # Collect lines until we find one ending with }
            combined = trimmed
            j = i + 1
            while j < len(lines) and not combined.endswith("}"):
                combined += "\\n" + lines[j].strip()
                j += 1

            # Try to parse the reconstructed JSON
            fixed_tool = parse_tool_json_line(combined)
            if fixed_tool:
                tools.append(fixed_tool)

    return tools


def find_invalid_tool_line(text: str) -> Optional[str]:
    """Find invalid tool call line in text.

    Args:
        text: Model response text

    Returns:
        Invalid line if found, None otherwise
    """
    lines = text.split("\n")
    for raw in lines:
        line = raw.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        if '"tool"' not in line:
            continue
        if '"cmd"' not in line and '"path"' not in line:
            continue
        if not parse_tool_json_line(line):
            return line
    return None


def find_unsupported_tool_line(text: str) -> Optional[str]:
    """Find unsupported tool name in text.

    Args:
        text: Model response text

    Returns:
        Unsupported tool name if found, None otherwise
    """
    lines = text.split("\n")
    supported_tools = ["run", "write"]
    for raw in lines:
        line = raw.strip()
        if not line.startswith("{") or not line.endswith("}"):
            continue
        if '"tool"' not in line:
            continue
        try:
            obj = json.loads(line)
            if obj and isinstance(obj.get("tool"), str) and obj["tool"] not in supported_tools:
                return obj["tool"]
        except json.JSONDecodeError:
            continue
    return None


def has_code_blocks(text: str) -> bool:
    """Check if text contains markdown code blocks.

    Args:
        text: Model response text

    Returns:
        True if code blocks found
    """
    return bool(re.search(r"```\w*\n[\s\S]*?```", text))


def is_noop_echo(cmd: str) -> bool:
    """Check if command is a no-op echo (just prints, doesn't write).

    Args:
        cmd: Command string

    Returns:
        True if it's a no-op echo command
    """
    trimmed = cmd.strip()
    if not trimmed.startswith("echo "):
        return False
    if ">" in trimmed or ">>" in trimmed or "|" in trimmed:
        return False
    return True


def is_git_repo(root: str) -> bool:
    """Check if directory is a git repository.

    Args:
        root: Directory path

    Returns:
        True if it's a git repo
    """
    git_path = Path(root) / ".git"
    return git_path.exists() and (git_path.is_dir() or git_path.is_file())


def parse_todo_list(text: str) -> Optional[List[str]]:
    """Parse TODO list from text.

    Args:
        text: Model response text

    Returns:
        List of TODO items if valid TODO list found, None otherwise
    """
    # Strip code block markers if present
    cleaned = re.sub(r"^```\w*\n?", "", text, flags=re.MULTILINE)
    cleaned = re.sub(r"```$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.strip()

    if not re.search(r"^TODO:\s*$", cleaned, re.MULTILINE | re.IGNORECASE):
        return None

    items = []
    for match in re.finditer(r"^- \[ \] (.+)$", cleaned, re.MULTILINE):
        items.append(match.group(1).strip())

    return items if items else None


def looks_like_clarifying_question(text: str) -> bool:
    """Check if text looks like a clarifying question.

    Args:
        text: Model response text

    Returns:
        True if text looks like a question
    """
    lower = text.lower()
    if "?" not in text:
        return False
    if re.search(r"^TODO:\s*$", text, re.MULTILINE | re.IGNORECASE):
        return False

    for indicator in QUESTION_INDICATORS:
        if indicator in lower:
            return True
    return False


def format_todo_list(items: List[str], done_index: int) -> str:
    """Format TODO list with checkmarks.

    Args:
        items: List of TODO items
        done_index: Index of last completed item (-1 for none)

    Returns:
        Formatted TODO list string
    """
    lines = ["TODO:"]
    for i, item in enumerate(items):
        checked = "x" if i <= done_index else " "
        lines.append(f"- [{checked}] {item}")
    return "\n".join(lines)


def run_command(cmd: str, cwd: str, timeout: int = 10) -> Dict[str, Any]:
    """Run a shell command.

    Args:
        cmd: Command to run
        cwd: Working directory
        timeout: Timeout in seconds

    Returns:
        Result dict with exitCode, stdout, stderr, timedOut, truncated
    """
    # Simple denylist for dangerous commands
    dangerous_patterns = [
        r"\brm\s+-rf\s+\/(\s|$)",
        r"\bmkfs\b",
        r"\bdd\s+if=",
        r"\bshutdown\b",
        r"\breboot\b",
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, cmd):
            return {
                "exitCode": 1,
                "stdout": "",
                "stderr": "Command blocked by safety denylist. Contains dangerous pattern.",
                "timedOut": False,
                "truncated": False,
            }

    try:
        result = subprocess.run(
            ["/bin/bash", "-c", cmd],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        stdout = result.stdout
        stderr = result.stderr
        truncated = False

        # Apply output limits
        if len(stdout) > MAX_OUTPUT_CHARS:
            stdout = stdout[:MAX_OUTPUT_CHARS] + "\n\n... output truncated ..."
            truncated = True

        lines = stdout.split("\n")
        if len(lines) > MAX_OUTPUT_LINES:
            stdout = "\n".join(lines[:MAX_OUTPUT_LINES]) + "\n\n... output truncated ..."
            truncated = True

        return {
            "exitCode": result.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timedOut": False,
            "truncated": truncated,
        }
    except subprocess.TimeoutExpired:
        return {
            "exitCode": -1,
            "stdout": "",
            "stderr": f"Command timed out after {timeout} seconds",
            "timedOut": True,
            "truncated": False,
        }
    except Exception as e:
        return {
            "exitCode": -1,
            "stdout": "",
            "stderr": f"Error executing command: {e}",
            "timedOut": False,
            "truncated": False,
        }


def format_tool_result(result: Dict[str, Any]) -> str:
    """Format tool result for display.

    Args:
        result: Result dict from run_command

    Returns:
        Formatted result string
    """
    lines = []
    if result.get("timedOut"):
        lines.append("timedOut: true")
    if result.get("truncated"):
        lines.append("truncated: true")
    lines.append(f"exitCode: {result['exitCode']}")
    lines.append("stdout:")
    lines.append(result.get("stdout", ""))
    lines.append("stderr:")
    lines.append(result.get("stderr", ""))
    return "\n".join(lines)


def write_file(path: str, content: str, cwd: str) -> str:
    """Write content to a file.

    Args:
        path: File path (relative to cwd)
        content: File content
        cwd: Working directory

    Returns:
        Result message
    """
    try:
        full_path = Path(cwd) / path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")
        return f"File written: {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def stream_chat(model: str, messages: List[Dict[str, str]], host: str) -> str:
    """Stream chat completion from Ollama.

    Args:
        model: Model name
        messages: List of message dicts
        host: Ollama host URL

    Returns:
        Full response text
    """
    url = f"{host}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
    }

    try:
        # Use longer timeout for initial connection (model loading) and reads
        # Connection timeout: 30s for model loading
        # Read timeout: 300s (5 min) for generation
        response = requests.post(url, json=payload, stream=True, timeout=(30, 300))
        response.raise_for_status()

        full_text = ""
        for line in response.iter_lines():
            if not line:
                continue

            line_str = line.decode("utf-8")
            if line_str.startswith("data: "):
                data_str = line_str[6:]
                if data_str.strip() in ["[DONE]", ""]:
                    continue

                try:
                    data = json.loads(data_str)
                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if delta:
                        print(delta, end="", flush=True)
                        full_text += delta

                        # Stop early if we detect a tool call
                        if extract_tool_calls(full_text):
                            return full_text

                except json.JSONDecodeError:
                    continue

        return full_text

    except requests.exceptions.RequestException as e:
        raise Exception(f"Error calling Ollama: {e}")


def list_models(host: str) -> List[str]:
    """List available models from Ollama.

    Args:
        host: Ollama host URL

    Returns:
        List of model names
    """
    try:
        response = requests.get(f"{host}/v1/models", timeout=5)
        response.raise_for_status()
        data = response.json()
        return [m["id"] for m in data.get("data", [])]
    except Exception:
        return []


def print_banner(model: str, host: str):
    """Print startup banner.

    Args:
        model: Model name
        host: Ollama host URL
    """
    print(f"{BLUE}patchpal-simple{RESET} - minimal CLI for small local models")
    print(f"server: {host}")
    print(f"model: {model}")
    print()


def main():
    """Main entry point for patchpal-simple."""
    # Parse arguments
    import argparse

    parser = argparse.ArgumentParser(
        description="Minimal CLI for small local Ollama models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", help="Model to use")
    parser.add_argument("--host", help="Ollama host URL")
    parser.add_argument("--root", help="Working directory", default=".")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-approve all prompts")
    parser.add_argument("prompt", nargs="*", help="Initial prompt to execute")

    args = parser.parse_args()

    # Configuration
    host = args.host or OLLAMA_HOST
    model = args.model or os.getenv("PATCHPAL_SIMPLE_MODEL", DEFAULT_MODEL)
    cwd = os.path.abspath(args.root)

    # Check Ollama is reachable
    models = list_models(host)
    if not models:
        print(f"{RED}✗ Cannot reach Ollama at {host}{RESET}")
        print(f"{YELLOW}  Is Ollama running? Try: ollama serve{RESET}")
        sys.exit(1)

    # Check if model exists
    if model not in models:
        print(f"{YELLOW}⚠️  Model '{model}' not found locally{RESET}")
        print(f"{YELLOW}  Available models: {', '.join(models)}{RESET}")
        print(f"{YELLOW}  Pull with: ollama pull {model}{RESET}")
        sys.exit(1)

    print_banner(model, host)

    # Git repo check
    if not is_git_repo(cwd):
        print(f"{YELLOW}(warn) current directory is not a git repository.{RESET}")
        if not args.yes:
            try:
                cont = input("Continue anyway? [y/N] ")
                if not cont or not re.match(r"^y(es)?$", cont.strip(), re.IGNORECASE):
                    print("Exiting.")
                    sys.exit(0)
                print()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                sys.exit(0)

    # Initialize conversation
    system_message = {"role": "system", "content": SYSTEM_PROMPT}
    messages = [system_message]
    todo_state = None

    # Handle SIGINT
    def sigint_handler(sig, frame):
        print("\n")
        sys.exit(0)

    import signal

    signal.signal(signal.SIGINT, sigint_handler)

    # Handle command-line prompt vs interactive
    first_input = None
    if args.prompt:
        first_input = " ".join(args.prompt)
        print(f"{BLUE}|{GRAY} {first_input}{RESET}\n")

    # Main loop
    while True:
        # Get user input
        if first_input:
            user_input = first_input
            first_input = None
        else:
            try:
                user_input = input(f"{BLUE}|{GRAY} ")
                print(RESET, end="")
            except (EOFError, KeyboardInterrupt):
                print()
                break

        if not user_input:
            continue
        print()

        # Handle slash commands
        if user_input.startswith("/"):
            if user_input == "/exit":
                break
            elif user_input == "/reset":
                messages = [system_message]
                todo_state = None
                print("(reset)")
                continue
            else:
                print("Unknown command. Try /exit, /reset")
                continue

        # Planning phase
        planner_input = user_input
        plan_approved = False

        while not plan_approved:
            print(f"{DIM}🤔 Planning...{RESET}", flush=True)
            planner_messages = [
                {"role": "system", "content": PLANNER_PROMPT},
                {"role": "user", "content": planner_input},
            ]

            try:
                plan_response = stream_chat(model, planner_messages, host)
                print()  # Newline after streaming
            except Exception as e:
                print(f"\n{RED}✗ Planner error: {e}{RESET}\n")
                break

            print()

            # Check for clarifying question
            if looks_like_clarifying_question(plan_response):
                if args.yes:
                    # Auto-proceed with defaults
                    planner_input = f"{user_input}\n\nUser clarification: Please proceed with reasonable defaults. Make your own choices for any details not specified."
                    continue

                try:
                    clarification = input(f"{BLUE}|{GRAY} ")
                    print(RESET, end="")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not clarification:
                    continue
                print()

                planner_input = f"{user_input}\n\nUser clarification: {clarification}"
                continue

            # Parse TODO list
            plan_items = parse_todo_list(plan_response)
            if not plan_items:
                # Retry with repair prompt
                print(f"{YELLOW}(planner did not produce a TODO list, retrying...){RESET}")
                planner_messages.append({"role": "assistant", "content": plan_response})
                planner_messages.append(
                    {
                        "role": "user",
                        "content": "Please respond with ONLY a TODO list in this exact format:\nTODO:\n- [ ] First step\n- [ ] Second step",
                    }
                )

                try:
                    plan_response = stream_chat(model, planner_messages, host)
                    print()
                except Exception as e:
                    print(f"\n{RED}✗ Planner retry error: {e}{RESET}\n")
                    break

                print()

                retry_items = parse_todo_list(plan_response)
                if not retry_items:
                    print(
                        f"{YELLOW}(planner could not produce a TODO list, proceeding without plan){RESET}\n"
                    )
                    plan_approved = True
                    todo_state = None
                    break

                plan_items = retry_items

            # Show TODO list
            print(f"{format_todo_list(plan_items, -1)}\n")

            # Ask for approval
            if args.yes:
                print("(auto-approved)\n")
                todo_state = {
                    "pending_list": False,
                    "items": plan_items,
                    "index": 0,
                    "goal": user_input,
                }
                plan_approved = True
                break

            try:
                approve = input("Execute this plan? [Y/n/e] ")
            except (EOFError, KeyboardInterrupt):
                print()
                break

            approve_text = approve.strip().lower()
            if approve_text in ["n", "no"]:
                print("(plan cancelled)\n")
                break
            elif approve_text in ["e", "edit"]:
                try:
                    edited = input(f"{BLUE}|{GRAY} ")
                    print(RESET, end="")
                except (EOFError, KeyboardInterrupt):
                    print()
                    break

                if not edited:
                    continue
                print()

                planner_input = edited
                continue
            else:
                # Approved (Y or Enter)
                todo_state = {
                    "pending_list": False,
                    "items": plan_items,
                    "index": 0,
                    "goal": user_input,
                }
                plan_approved = True
                break

        # If plan not approved, continue to next input
        if not plan_approved:
            continue

        # Add user message
        messages.append({"role": "user", "content": user_input})

        # If we have a todo state, inject the current step
        if todo_state and todo_state["items"]:
            messages.append(
                {
                    "role": "user",
                    "content": f"Goal: {user_input}\n\n{TOOL_REMINDER}\n\nStep {todo_state['index'] + 1} of {len(todo_state['items'])}: {todo_state['items'][todo_state['index']]}\n\nComplete ONLY this step, then stop.",
                }
            )

        # Execution loop
        tool_repair_attempts = 0
        max_iterations = 50

        for iteration in range(max_iterations):
            print(f"{DIM}🤔 Thinking...{RESET}", flush=True)

            try:
                response = stream_chat(model, messages, host)
                print()  # Newline after streaming
            except Exception as e:
                print(f"\n{RED}✗ Error: {e}{RESET}\n")
                break

            print()

            # Check if model re-output TODO list
            todo_items_in_text = parse_todo_list(response)
            if todo_state and not todo_state["pending_list"] and todo_items_in_text:
                # Model re-outputted TODO list during execution, suppress it
                messages.append({"role": "assistant", "content": response})
                messages.append(
                    {
                        "role": "user",
                        "content": "Do not output the TODO list again. I will track it. Continue with the current step.",
                    }
                )
                continue

            # Extract tool calls
            tools = extract_tool_calls(response)

            if not tools:
                # No tool calls - check if we need repair
                messages.append({"role": "assistant", "content": response})

                # Try various repair strategies
                invalid_line = find_invalid_tool_line(response)
                if invalid_line and tool_repair_attempts < 2:
                    tool_repair_attempts += 1
                    print(f"{DIM}(tool repair prompt){RESET}")
                    messages.append({"role": "user", "content": TOOL_REPAIR_PROMPT})
                    continue

                unsupported_tool = find_unsupported_tool_line(response)
                if unsupported_tool and tool_repair_attempts < 2:
                    tool_repair_attempts += 1
                    print(f"{DIM}(tool repair prompt){RESET}")
                    messages.append({"role": "user", "content": TOOL_REPAIR_PROMPT})
                    continue

                # Check if looks like a tool call but couldn't parse
                looks_like_tool = '"tool"' in response and (
                    '"run"' in response or '"write"' in response
                )
                if looks_like_tool and tool_repair_attempts < 3:
                    tool_repair_attempts += 1
                    print(f"{DIM}(tool repair prompt){RESET}")
                    messages.append({"role": "user", "content": TOOL_REPAIR_PROMPT})
                    continue

                # Check for code blocks
                if has_code_blocks(response) and tool_repair_attempts < 3:
                    tool_repair_attempts += 1
                    print(f"{DIM}(code block detected){RESET}")
                    messages.append({"role": "user", "content": CODE_BLOCK_REPAIR_PROMPT})
                    continue

                # Check if we need to advance TODO
                if todo_state and todo_state["index"] < len(todo_state["items"]):
                    print(f"{format_todo_list(todo_state['items'], todo_state['index'])}\n")
                    todo_state["index"] += 1
                    if todo_state["index"] >= len(todo_state["items"]):
                        todo_state = None
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Goal: {todo_state['goal']}\n\n{TOOL_REMINDER}\n\nStep {todo_state['index'] + 1} of {len(todo_state['items'])}: {todo_state['items'][todo_state['index']]}\n\nOutput ONLY the tool call JSON, no explanation. Complete ONLY this step, then stop.",
                        }
                    )
                    continue

                # Done
                break

            # Execute first tool only
            messages.append({"role": "assistant", "content": response})
            first_tool = tools[0]
            has_multiple_tools = len(tools) > 1

            # Skip noop echo commands
            if first_tool["tool"] == "run" and is_noop_echo(first_tool["cmd"]):
                messages.append(
                    {
                        "role": "tool",
                        "name": "run",
                        "content": "One or more echo-only tool calls were skipped.",
                    }
                )
                continue

            # Handle run tool
            if first_tool["tool"] == "run":
                cmd = first_tool["cmd"]
                print(f"{RED}{cmd}{RESET}")

                # Ask for approval (unless --yes)
                run_approved = True
                if not args.yes:
                    try:
                        approve = input("Run? [Y/n] ")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break

                    approve_text = approve.strip()
                    if approve_text and not re.match(r"^y(es)?$", approve_text, re.IGNORECASE):
                        run_approved = False
                        messages.append(
                            {
                                "role": "tool",
                                "name": "run",
                                "content": "Command not run (user denied).",
                            }
                        )

                        # Ask for feedback
                        try:
                            feedback = input(f"{BLUE}|{GRAY} ")
                            print(RESET, end="")
                        except (EOFError, KeyboardInterrupt):
                            print()
                            break

                        if feedback:
                            print()
                            messages.append({"role": "user", "content": feedback})
                        else:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": "Try a different approach for this step.",
                                }
                            )

                if not run_approved:
                    continue

                print()

                # Execute command
                result = run_command(cmd, cwd)
                result_str = format_tool_result(result)

                messages.append({"role": "tool", "name": "run", "content": result_str})

                # Auto-advance TODO in --yes mode
                if todo_state and args.yes and result["exitCode"] == 0:
                    print(f"{format_todo_list(todo_state['items'], todo_state['index'])}\n")
                    todo_state["index"] += 1
                    if todo_state["index"] >= len(todo_state["items"]):
                        todo_state = None
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Goal: {todo_state['goal']}\n\n{TOOL_REMINDER}\n\nStep {todo_state['index'] + 1} of {len(todo_state['items'])}: {todo_state['items'][todo_state['index']]}\n\nOutput ONLY the tool call JSON, no explanation. Complete ONLY this step, then stop.",
                        }
                    )
                    continue

                # Prompt verification for write operations
                is_read_only = re.match(
                    r"^\s*(cat|ls|head|tail|grep|find|wc|file|stat|pwd|echo|tree)\s", cmd
                )
                if result["exitCode"] == 0 and not is_read_only:
                    messages.append(
                        {
                            "role": "user",
                            "content": "If that was a write operation, verify it succeeded. Then continue with your task.",
                        }
                    )

                # Remind about one-at-a-time if multiple tools
                if has_multiple_tools:
                    messages.append(
                        {
                            "role": "user",
                            "content": "REMINDER: Output ONE tool call per response. I executed only the first one. Continue with your next action.",
                        }
                    )

            # Handle write tool
            elif first_tool["tool"] == "write":
                path = first_tool["path"]
                content = first_tool["content"]

                # Show preview
                preview = content[:200]
                if len(content) > 200:
                    preview += "..."
                print(f"{RED}write: {path}{RESET}")
                print(preview)

                # Ask for approval (unless --yes)
                write_approved = True
                if not args.yes:
                    try:
                        approve = input("Write? [Y/n] ")
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break

                    approve_text = approve.strip()
                    if approve_text and not re.match(r"^y(es)?$", approve_text, re.IGNORECASE):
                        write_approved = False
                        messages.append(
                            {
                                "role": "tool",
                                "name": "write",
                                "content": "File not written (user denied).",
                            }
                        )

                        # Ask for feedback
                        try:
                            feedback = input(f"{BLUE}|{GRAY} ")
                            print(RESET, end="")
                        except (EOFError, KeyboardInterrupt):
                            print()
                            break

                        if feedback:
                            print()
                            messages.append({"role": "user", "content": feedback})
                        else:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": "Try a different approach for this step.",
                                }
                            )

                if not write_approved:
                    continue

                print()

                # Write file
                result_str = write_file(path, content, cwd)
                messages.append({"role": "tool", "name": "write", "content": result_str})

                # Auto-advance TODO in --yes mode
                if todo_state and args.yes:
                    print(f"{format_todo_list(todo_state['items'], todo_state['index'])}\n")
                    todo_state["index"] += 1
                    if todo_state["index"] >= len(todo_state["items"]):
                        todo_state = None
                        break
                    messages.append(
                        {
                            "role": "user",
                            "content": f"Goal: {todo_state['goal']}\n\n{TOOL_REMINDER}\n\nStep {todo_state['index'] + 1} of {len(todo_state['items'])}: {todo_state['items'][todo_state['index']]}\n\nComplete ONLY this step, then stop.",
                        }
                    )
                    continue

                # Prompt verification
                verify_msg = "Verify the file was written correctly, then continue with your task."
                if has_multiple_tools:
                    verify_msg += " REMINDER: Output ONE tool call per response. I executed only the first one."
                messages.append({"role": "user", "content": verify_msg})

            # Continue execution loop
            continue

        # Exit if running with prompt argument
        if args.prompt:
            break

    print(f"{DIM}Goodbye!{RESET}")


if __name__ == "__main__":
    main()
