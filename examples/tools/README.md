# Custom Tools Examples

This directory contains example custom tools that demonstrate how to extend PatchPal with Python functions.

## What Are Custom Tools?

Custom tools are Python functions that the PatchPal agent can call automatically. Unlike skills (which are prompt-based workflows), custom tools execute actual Python code and return results.

## Quick Start

### Global Tools (Available in all projects)

**1. Create the tools directory:**
```bash
mkdir -p ~/.patchpal/tools
```

**2. Copy the example:**
```bash
cp calculator.py ~/.patchpal/tools/
```

### Repository-Specific Tools (Project-specific)

**1. Create the repository tools directory:**
```bash
mkdir -p .patchpal/tools
```

**2. Copy or create tools:**
```bash
cp calculator.py .patchpal/tools/
```

### Start PatchPal

**3. Start PatchPal:**
```bash
patchpal
```

You'll see:
```
🔧 Loaded 7 custom tool(s): add, subtract, multiply, divide, calculate_percentage, fahrenheit_to_celsius, celsius_to_fahrenheit
```

**4. Use your tools:**
```
You: What's 25 + 17?
Agent: [Calls add tool automatically]
        25 + 17 = 42

You: Convert 72°F to Celsius
Agent: [Calls fahrenheit_to_celsius tool]
        72°F = 22.22°C
```

## Tool Requirements

Custom tools must have:

1. ✅ **Type hints** for all parameters
2. ✅ **Docstring** with description and `Args:` section
3. ✅ **Module-level** functions (not nested in classes)
4. ✅ **Return string** for LLM consumption

**Example:**
```python
def add(x: int, y: int) -> str:
    """Add two numbers together.

    Args:
        x: First number
        y: Second number
    """
    result = x + y
    return f"{x} + {y} = {result}"
```

## What Gets Loaded?

- ✅ Functions with type hints and docstrings
- ✅ Multiple functions per file
- ✅ Standard library imports
- ❌ Functions without type hints
- ❌ Functions without docstrings
- ❌ Private functions (starting with `_`)
- ❌ Imported functions from other modules

## Available Example Tools

### calculator.py
Basic arithmetic and temperature conversion (7 tools):
- `add(x, y)` - Add two integers
- `subtract(x, y)` - Subtract two integers
- `multiply(x, y)` - Multiply two floats
- `divide(x, y)` - Divide two floats (with zero check)
- `calculate_percentage(value, percentage)` - Calculate percentage of value
- `fahrenheit_to_celsius(fahrenheit)` - Convert F to C
- `celsius_to_fahrenheit(celsius)` - Convert C to F

### system_tools.py
Get system information and analyze disk usage (6 tools):
- `get_disk_usage(path)` - Show disk usage statistics for a path
- `get_system_info()` - Get OS, Python version, and architecture info
- `get_env_var(var_name)` - Get an environment variable (masks sensitive values)
- `list_env_vars(filter_pattern)` - List environment variables with optional filter
- `get_directory_size(directory)` - Calculate total size of a directory
- `check_path_exists(path)` - Check if path exists and show info

**Requirements:** No external dependencies (uses Python standard library)

**Example usage:**
```
You: What's the disk usage for the current directory?
Agent: [Calls get_disk_usage(".")]

You: Show me system information
Agent: [Calls get_system_info()]

You: What's the value of PATH?
Agent: [Calls get_env_var("PATH")]

You: How big is the examples directory?
Agent: [Calls get_directory_size("examples")]
```

### github_tools.py
Search and get information from GitHub API (3 tools):
- `search_github_repos(query, language, max_results)` - Search repositories
- `get_github_user(username)` - Get user profile information
- `get_repo_info(owner, repo)` - Get detailed repository info

**Requirements:** `pip install requests`

**Example usage:**
```
You: Search for Python machine learning repos
Agent: [Calls search_github_repos("machine learning", "Python", 5)]

You: Get info about torvalds
Agent: [Calls get_github_user("torvalds")]

You: Show details for amaiya/patchpal
Agent: [Calls get_repo_info("amaiya", "patchpal")]
```

## Creating Your Own Tools

**Simple example:**
```python
# ~/.patchpal/tools/my_tools.py

def reverse_text(text: str) -> str:
    """Reverse a string.

    Args:
        text: Text to reverse
    """
    return text[::-1]


def count_words(text: str) -> str:
    """Count words in text.

    Args:
        text: Text to analyze
    """
    word_count = len(text.split())
    return f"Word count: {word_count}"
```

**Advanced example with Optional parameters:**
```python
from typing import Optional

def greet(name: str, greeting: Optional[str] = "Hello") -> str:
    """Greet someone.

    Args:
        name: Person's name
        greeting: Optional greeting message (default: "Hello")
    """
    return f"{greeting}, {name}!"
```

**Complex types:**
```python
from typing import List

def sum_list(numbers: List[int]) -> str:
    """Sum a list of numbers.

    Args:
        numbers: List of integers to sum
    """
    total = sum(numbers)
    return f"Sum: {total}"
```

## Security Note

⚠️ Custom tools execute Python code on your system. Only install tools from trusted sources.

**Tool Locations:**
- **Global tools**: `~/.patchpal/tools/` - Available in all projects
- **Repository-specific tools**: `<repo>/.patchpal/tools/` - Project-specific tools

**Security Considerations:**
- Review code before installing any custom tools
- Repository-specific tools make it easy to share project functionality
- Be cautious when cloning repositories - check `.patchpal/tools/` for custom tools
- Repository tools override global tools with the same name

## Troubleshooting

**Tools not loading?**

1. Check file has `.py` extension
2. Ensure all parameters have type hints
3. Verify docstring has `Args:` section (Google style)
4. Look for warning messages when starting PatchPal
5. Test function in Python: `python -c "from my_tools import my_func"`

**Example error:**
```bash
⚠️  Warning: Failed to load custom tool from broken.py: missing type hints
```

## Usage in Python API

Custom tools work the same way in the Python API:

```python
from patchpal.agent import create_agent

def calculator(x: int, y: int) -> str:
    """Add numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)

agent = create_agent(custom_tools=[calculator])
response = agent.run("What's 5 + 3?")
```

## Learn More

- **Full Documentation**: See main README.md "Custom Tools" section
- **Tool Schema Details**: `patchpal/tool_schema.py`
- **Test Examples**: `tests/test_custom_tools.py`

## Real-World Tool Ideas

**API Integration:**
```python
def get_weather(city: str) -> str:
    """Get weather for a city (requires API key)."""
    # Call weather API
    pass
```

**Database Queries:**
```python
def query_users(limit: int = 10) -> str:
    """Query database for users."""
    # Execute SQL query
    pass
```

**File Processing:**
```python
def parse_csv(filepath: str) -> str:
    """Parse CSV file and return summary."""
    import csv
    # Process file
    pass
```

**System Information:**
```python
def disk_usage() -> str:
    """Get disk usage statistics."""
    import shutil
    # Return stats
    pass
```

The agent will automatically discover and use your tools when they're relevant to the user's request!
