# Repository Map Feature

## Overview

The `get_repo_map` tool provides a **consolidated view** of your entire codebase, showing function and class signatures from all files without their implementations. This is inspired by [aider's repomap feature](https://aider.chat/docs/repomap.html) and provides **38-70% token savings** compared to calling `code_structure` on each file individually.

## Why Use Repository Map?

### Token Efficiency

**Traditional Approach:**
- Call `code_structure()` on 20 files individually
- 20 separate outputs with redundant formatting
- **4,916 tokens total**

**With Repository Map:**
- Single call to `get_repo_map()`
- Combined output with streamlined formatting
- **1,459 tokens total**
- **Savings: 70.3%**

### Real-World Savings

Based on actual tests with the PatchPal repository:

| Files | code_structure (individual) | get_repo_map (combined) | Savings |
|-------|---------------------------|------------------------|---------|
| 20 files | 4,916 tokens | 1,459 tokens | **70.3%** |
| 37 files | 8,052 tokens | 4,988 tokens | **38.1%** |

**Why the range?** Savings depend on file complexity:
- Simple files (tests, scripts): 70%+ savings
- Complex files (large classes): 38-50% savings

### When to Use

Use `get_repo_map` when you need to:
- **Understand** the overall codebase structure
- **Discover** relevant files without reading them all
- **Orient yourself** in an unfamiliar codebase
- **Find** related code across the project
- **Explore** a large project efficiently

## Supported Languages

The repository map supports **20+ languages** automatically:

- Python, JavaScript, TypeScript
- Go, Rust, Java, C/C++, C#
- Ruby, PHP, Swift, Kotlin, Scala
- Elm, Elixir, R, Bash
- And more!

Language detection is automatic based on file extensions.

## Usage

### Basic Usage

```python
from patchpal.tools import get_repo_map

# Get a map of up to 100 files
repo_map = get_repo_map(max_files=100)
print(repo_map)
```

### Filter by Language

```python
# Only show Python files
repo_map = get_repo_map(
    max_files=50,
    include_patterns=["*.py"]
)

# Only show JavaScript/TypeScript
repo_map = get_repo_map(
    max_files=50,
    include_patterns=["*.js", "*.ts", "*.jsx", "*.tsx"]
)
```

### Exclude Patterns

```python
# Exclude tests and generated code
repo_map = get_repo_map(
    max_files=100,
    exclude_patterns=[
        "*test*",           # Exclude test files
        "*_pb2.py",         # Exclude protobuf generated files
        "vendor/**",        # Exclude vendor directory
        "node_modules/**"   # Exclude node_modules
    ]
)
```

### Focus Files

```python
# Prioritize specific files (they appear first)
repo_map = get_repo_map(
    max_files=100,
    focus_files=[
        "src/main.py",
        "src/config.py"
    ]
)
```

### Combined Example

```python
# Python backend, exclude tests, focus on auth
repo_map = get_repo_map(
    max_files=75,
    include_patterns=["src/**/*.py"],
    exclude_patterns=["*test*", "*__pycache__*"],
    focus_files=["src/auth/login.py"]
)
```

## Example Output

```
Repository Map (42 files analyzed, showing 42):

src/auth/login.py:
  Line   23: def authenticate(username: str, password: str) -> bool
  Line   45: def check_password(hashed: str, password: str) -> bool
  Line   67: class LoginManager:
            70:   def __init__(self, config: Config):
            75:   def login(self, credentials: Credentials) -> Token:

src/auth/token.py:
  Line   12: class Token:
            15:   def __init__(self, user_id: int, expires: datetime):
            20:   def is_valid(self) -> bool
  Line   30: def generate_token(user_id: int) -> Token
  Line   45: def verify_token(token: str) -> Optional[User]

src/database/models.py:
  Line   15: class User:
            18:   def __init__(self, id: int, username: str):
            25:   def to_dict(self) -> dict
  Line   35: class Session:
            38:   def __init__(self, user: User, token: Token):

💡 Use code_structure(path) to see full details for a specific file
💡 Use read_file(path) to see complete implementation
```

## Workflow Recommendations

### 1. Start with Repository Map

```python
# First, get the big picture
repo_map = get_repo_map(max_files=100)

# Identify relevant files from the map
# Then read specific files
from patchpal.tools import read_file
content = read_file("src/auth/login.py")
```

### 2. Narrow Down with Patterns

```python
# Start broad
repo_map = get_repo_map(max_files=100)

# Then narrow down to specific area
auth_map = get_repo_map(
    max_files=50,
    include_patterns=["src/auth/**/*.py"]
)
```

### 3. Use with Code Structure

```python
# Get overview of all files
repo_map = get_repo_map(max_files=100)

# Deep dive into specific file
from patchpal.tools import code_structure
details = code_structure("src/auth/login.py", max_symbols=100)
```

## Caching

The repository map uses **intelligent caching** based on file modification times:

```python
from patchpal.tools import get_repo_map_stats, clear_repo_map_cache

# Check cache stats
stats = get_repo_map_stats()
print(f"Cached files: {stats['cached_files']}")
print(f"Cache age: {stats['cache_age']:.1f} seconds")

# Clear cache if needed (e.g., after external changes)
clear_repo_map_cache()
```

Cache benefits:
- **Fast repeated calls**: Second call reuses parsed results
- **Automatic invalidation**: Cache updates when files change
- **Memory efficient**: Only caches file structures, not full content

## Integration with PatchPal CLI

When using PatchPal interactively, the agent automatically uses `get_repo_map` to understand your codebase efficiently:

```bash
$ patchpal

You: Where is the authentication logic?

# Agent calls get_repo_map() to scan the codebase
# Then responds with relevant file locations
# Without reading every file individually
```

## Performance Notes

- **Large repositories**: Use `max_files` to limit scope
- **First scan**: May take a few seconds (builds cache)
- **Subsequent scans**: Nearly instant (uses cache)
- **Memory usage**: Minimal (caches signatures only, not full files)

## Comparison to Other Tools

| Tool | Tokens for 50 Files | Coverage | Speed |
|------|-------------------|----------|-------|
| `list_files` | 500 | File names only | Instant |
| `get_repo_map` | 7,500 | Function/class signatures | Fast |
| `code_structure` × 50 | 25,000 | Full file structures | Slow |
| `read_file` × 50 | 100,000 | Complete implementations | Very slow |

## Tips

1. **Start broad, narrow down**: Begin with a full repo map, then focus on specific areas
2. **Exclude noise**: Use `exclude_patterns` to filter out tests, generated code, and dependencies
3. **Use focus_files**: Prioritize files you're already discussing
4. **Combine with grep**: Use `get_repo_map` to find files, then `grep_code` to search content
5. **Check the cache**: If files change externally, clear the cache to force a refresh

## API Reference

### `get_repo_map(max_files, include_patterns, exclude_patterns, focus_files)`

Generate a compact repository map.

**Parameters:**
- `max_files` (int, default: 100): Maximum files to include
- `include_patterns` (list[str], optional): Glob patterns to include
- `exclude_patterns` (list[str], optional): Glob patterns to exclude
- `focus_files` (list[str], optional): Files to prioritize

**Returns:**
- `str`: Formatted repository map

### `get_repo_map_stats()`

Get cache statistics.

**Returns:**
- `dict`: Statistics with keys `cached_files`, `last_scan`, `cache_age`

### `clear_repo_map_cache()`

Clear the repository map cache.

**Returns:**
- `None`

## Learn More

- [Aider's RepoMap Documentation](https://aider.chat/docs/repomap.html)
- [Tree-sitter](https://tree-sitter.github.io/tree-sitter/) - The parser powering the map
- [PatchPal Documentation](../README.md)
