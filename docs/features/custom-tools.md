# Custom Tools

Custom tools extend PatchPal's capabilities by adding new Python functions that the agent can call. Unlike skills (which are prompt-based workflows), custom tools are executable Python code that the agent invokes automatically when needed.

**Key Differences:**
- **Skills**: Markdown files with instructions for the agent to follow
- **Custom Tools**: Python functions that execute code and return results

## Installation

Custom tools can be installed globally (available in all projects) or locally (specific to a repository).

### Global Tools

1. **Create the global tools directory:**
```bash
mkdir -p ~/.patchpal/tools
```

2. **Copy the example tools (or create your own):**
```bash
# After pip install patchpal, get the example tools
curl -L https://github.com/amaiya/patchpal/archive/main.tar.gz | tar xz --strip=1 patchpal-main/examples

# Copy to your tools directory
cp examples/tools/calculator.py ~/.patchpal/tools/
```

### Repository-Specific Tools

For project-specific tools that shouldn't be available globally:

1. **Create the repository tools directory:**
```bash
mkdir -p .patchpal/tools
```

2. **Add your custom tools:**
```bash
# Example: Create a project-specific tool
cat > .patchpal/tools/project_tool.py << 'EOF'
def get_project_info(key: str) -> str:
    """Get project-specific information.

    Args:
        key: Information key to retrieve
    """
    info = {"name": "MyProject", "version": "1.0.0"}
    return info.get(key, "Unknown")
EOF
```

3. **Tools are loaded automatically:**
```bash
$ patchpal
================================================================================
PatchPal - AI coding and automation assistant
================================================================================

Using model: anthropic/claude-sonnet-4-5
🔧 Loaded 8 custom tool(s): add, subtract, multiply, divide, calculate_percentage, fahrenheit_to_celsius, celsius_to_fahrenheit, get_project_info
```

**Note:** Repository-specific tools with the same name will override global tools.

## Creating Custom Tools

Custom tools are Python functions with specific requirements:

**Requirements:**
1. **Type hints** for all parameters
2. **Docstring** with description and Args section (Google-style)
3. **Module-level** functions (not nested inside classes)
4. **Return type** should typically be `str` (for LLM consumption)
5. Function names **cannot start with underscore** (private functions ignored)

**Example:**

```python
# ~/.patchpal/tools/my_tools.py

def calculator(x: int, y: int, operation: str = "add") -> str:
    """Perform basic arithmetic operations.

    Args:
        x: First number
        y: Second number
        operation: Operation to perform (add, subtract, multiply, divide)

    Returns:
        Result as a string
    """
    if operation == "add":
        return f"{x} + {y} = {x + y}"
    elif operation == "subtract":
        return f"{x} - {y} = {x - y}"
    elif operation == "multiply":
        return f"{x} * {y} = {x * y}"
    elif operation == "divide":
        if y == 0:
            return "Error: Cannot divide by zero"
        return f"{x} / {y} = {x / y}"
    return "Unknown operation"


def convert_currency(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert between currencies.

    Args:
        amount: Amount to convert
        from_currency: Source currency code (e.g., USD)
        to_currency: Target currency code (e.g., EUR)

    Returns:
        Converted amount as a string
    """
    # Your implementation here (API call, etc.)
    # This is just a simple example
    rates = {"USD": 1.0, "EUR": 0.85, "GBP": 0.73}
    usd_amount = amount / rates.get(from_currency, 1.0)
    result = usd_amount * rates.get(to_currency, 1.0)
    return f"{amount} {from_currency} = {result:.2f} {to_currency}"
```

## Using Custom Tools

Once loaded, the agent calls your custom tools automatically:

```bash
You: What's 15 + 27?
Agent: [Calls calculator(15, 27, "add")]
        15 + 27 = 42

You: What's 100 divided by 4?
Agent: [Calls calculator(100, 4, "divide")]
        100 / 4 = 25

You: Convert 100 USD to EUR
Agent: [Calls convert_currency(100, "USD", "EUR")]
        100 USD = 85.00 EUR
```

## Tool Discovery

PatchPal discovers tools from two locations at startup:

1. **Global tools**: `~/.patchpal/tools/*.py` - Available in all projects
2. **Repository-specific tools**: `<repo>/.patchpal/tools/*.py` - Only available in that repository

All `.py` files in these directories are scanned for valid tool functions. Repository-specific tools with the same name will override global tools.

**What Gets Loaded:**
- ✅ Functions with type hints and docstrings
- ✅ Multiple functions per file
- ✅ Files can import standard libraries
- ❌ Functions without type hints
- ❌ Functions without docstrings
- ❌ Private functions (starting with `_`)
- ❌ Imported functions (must be defined in the file)

## Example Tools

The repository includes [example tools](https://github.com/amaiya/patchpal/tree/main/examples/tools) that demonstrate different use cases:

### calculator.py

Basic arithmetic and temperature conversion (7 tools):

- `add(x, y)` - Add two integers
- `subtract(x, y)` - Subtract two integers
- `multiply(x, y)` - Multiply two floats
- `divide(x, y)` - Divide two floats (with zero check)
- `calculate_percentage(value, percentage)` - Calculate percentage of value
- `fahrenheit_to_celsius(fahrenheit)` - Convert F to C
- `celsius_to_fahrenheit(celsius)` - Convert C to F

**Requirements:** No external dependencies (uses Python standard library)

**Example usage:**
```
You: What's 25 + 17?
Agent: [Calls add tool automatically]
        25 + 17 = 42

You: Convert 72°F to Celsius
Agent: [Calls fahrenheit_to_celsius tool]
        72°F = 22.22°C
```

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

View the [examples/tools/](https://github.com/amaiya/patchpal/tree/main/examples/tools) directory for complete source code.

## Real-World Tool Ideas

Here are some ideas for custom tools you might create:

**API Integration:**
```python
def get_weather(city: str) -> str:
    """Get current weather for a city.

    Args:
        city: City name
    """
    # Call weather API (e.g., OpenWeatherMap)
    # Return formatted weather information
    pass
```

**Database Queries:**
```python
def query_users(limit: int = 10) -> str:
    """Query database for users.

    Args:
        limit: Maximum number of users to return
    """
    # Execute SQL query
    # Return formatted results
    pass
```

**File Processing:**
```python
def parse_csv(filepath: str) -> str:
    """Parse CSV file and return summary.

    Args:
        filepath: Path to CSV file
    """
    import csv
    # Process file and return statistics
    pass
```

**System Operations:**
```python
def backup_directory(source: str, destination: str) -> str:
    """Create a backup of a directory.

    Args:
        source: Source directory path
        destination: Backup destination path
    """
    import shutil
    # Create backup and return status
    pass
```

The agent will automatically discover and use your tools when they're relevant to the user's request!

## Security Note

⚠️ Custom tools execute arbitrary Python code on your system. Only install tools from sources you trust.

**Tool Locations:**
- **Global tools**: `~/.patchpal/tools/` - Your personal tools directory
- **Repository-specific tools**: `<repo>/.patchpal/tools/` - Project-specific tools

**Security Considerations:**
- Tools run with your user permissions
- Repository-specific tools make it easy to share project-specific functionality
- Review tools in `.patchpal/tools/` when cloning repositories
- Repository tools override global tools with the same name

## Advanced Features

**Optional Parameters:**
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

**Complex Types:**
```python
from typing import List

def sum_numbers(numbers: List[int]) -> str:
    """Sum a list of numbers.

    Args:
        numbers: List of integers to sum
    """
    total = sum(numbers)
    return f"Sum of {numbers} = {total}"
```

## Using Custom Tools in Python API

Custom tools can also be used programmatically when using PatchPal as a library:

```python
from patchpal.agent import create_agent

def calculator(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)

def get_user_count() -> str:
    """Get the current user count from database.

    Returns:
        User count as a string
    """
    # Your database logic here
    return "Total users: 1,234"

# Create agent with custom tools
agent = create_agent(custom_tools=[calculator, get_user_count])

# The agent can now use these tools automatically
response = agent.run("What's 5 + 3?")
# Agent will call calculator(5, 3) automatically

response = agent.run("How many users do we have?")
# Agent will call get_user_count() automatically
```

See the [Python API documentation](../api/usage.md) for more details.

## Troubleshooting

If tools aren't loading:
1. Check the file has a `.py` extension
2. Ensure functions have type hints for all parameters
3. Verify docstrings follow Google style (with Args: section)
4. Look for warning messages when starting PatchPal
5. Test the function directly in Python to check for syntax errors

**Example warning message:**
```
⚠️  Warning: Failed to load custom tool from broken.py: missing type hints
```
