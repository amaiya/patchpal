# PatchPal - A Claude Code Clone

An educational implementation of a Claude Code-like agent using smolagents.

## Installation

Install PatchPal from PyPI:

```bash
pip install patchpal
```

Or install from source:

```bash
git clone https://github.com/amaiya/patchpal.git
cd patchpal
pip install -e .
```

## Setup

1. **Get an Anthropic API key**:
   - Sign up at https://console.anthropic.com/
   - Generate an API key from your account settings

2. **Set up your API key**:
```bash
export ANTHROPIC_API_KEY=your_api_key_here
```

3. **Run PatchPal**:
```bash
patchpal
```

## Features

The agent has the following tools:

- **read_file**: Read contents of files in the repository
- **list_files**: List all files in the repository
- **apply_patch**: Modify files by providing new content
- **run_shell**: Execute safe shell commands (forbidden: rm, mv, sudo, etc.)

## Usage

Simply run the `patchpal` command and type your requests interactively:

```bash
$ patchpal
================================================================================
PatchPal - Claude Code Clone
================================================================================

Type 'exit' or 'quit' to exit the program.

You: Add type hints and basic logging to my_module.py
```

The agent will process your request and show you the results. You can continue with follow-up tasks or type `exit` to quit.

## Example Tasks

```
Add type hints and basic logging to app.py
Fix the divide by zero error in calculator.py
Create unit tests for the utils module
Refactor the authentication code for better security
Add error handling to all API calls
```

## Safety

The agent operates within a sandboxed environment with several restrictions:

- All file operations are restricted to the repository root
- Dangerous shell commands are blocked (rm, mv, sudo, etc.)
- All changes require passing through the apply_patch function
- Shell commands run with limited permissions

## Development

Install in development mode with dev dependencies:

```bash
pip install -e ".[dev]"
```

## Package Structure

```
patchpal/
├── __init__.py  - Package exports
├── tools.py     - Tool implementations (read, write, shell)
├── agent.py     - Agent configuration
└── cli.py       - CLI entry point
```

## Troubleshooting

**Error: "model: claude-3-5-sonnet-20240620"**
- Make sure your ANTHROPIC_API_KEY is set correctly
- Check that your API key has sufficient credits

**Error: "Invalid path"**
- The agent can only access files within the repository
- Use relative paths from the repository root

**Error: "Blocked command"**
- Some dangerous commands are forbidden for safety
- Check the FORBIDDEN list in tools.py
