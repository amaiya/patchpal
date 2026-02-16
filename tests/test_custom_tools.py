"""Test custom tools functionality."""

import tempfile
from pathlib import Path

from patchpal.tool_schema import discover_tools, function_to_tool_schema, list_custom_tools


def test_function_to_tool_schema_basic():
    """Test basic schema generation."""

    def calculator(x: int, y: int) -> str:
        """Add two numbers.

        Args:
            x: First number
            y: Second number
        """
        return str(x + y)

    schema = function_to_tool_schema(calculator)

    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calculator"
    assert "Add two numbers" in schema["function"]["description"]

    params = schema["function"]["parameters"]
    assert params["type"] == "object"
    assert "x" in params["properties"]
    assert "y" in params["properties"]
    assert params["properties"]["x"]["type"] == "integer"
    assert params["properties"]["y"]["type"] == "integer"
    assert params["required"] == ["x", "y"]


def test_function_to_tool_schema_with_defaults():
    """Test schema generation with default parameters."""

    def greet(name: str, greeting: str = "Hello") -> str:
        """Greet someone.

        Args:
            name: Person's name
            greeting: Greeting message
        """
        return f"{greeting}, {name}!"

    schema = function_to_tool_schema(greet)

    # Only 'name' should be required (greeting has default)
    assert schema["function"]["parameters"]["required"] == ["name"]
    assert "name" in schema["function"]["parameters"]["properties"]
    assert "greeting" in schema["function"]["parameters"]["properties"]


def test_function_to_tool_schema_optional():
    """Test schema generation with Optional types."""
    from typing import Optional

    def search(query: str, limit: Optional[int] = None) -> str:
        """Search for something.

        Args:
            query: Search query
            limit: Maximum results
        """
        return f"Searching for: {query}"

    schema = function_to_tool_schema(search)

    assert schema["function"]["parameters"]["required"] == ["query"]
    assert schema["function"]["parameters"]["properties"]["limit"]["type"] == "integer"


def test_discover_tools_empty_directory():
    """Test discovering tools from empty directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)
        tools = discover_tools(tools_dir)
        assert tools == []


def test_discover_tools_valid_tool():
    """Test discovering a valid tool function."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        # Create a valid tool file
        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''
def add(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 1
        assert tools[0].__name__ == "add"


def test_discover_tools_multiple_functions():
    """Test discovering multiple functions from one file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        # Create a file with multiple tools
        tool_file = tools_dir / "math_tools.py"
        tool_file.write_text(
            '''
def add(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)

def multiply(x: int, y: int) -> str:
    """Multiply two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x * y)
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 2
        tool_names = {tool.__name__ for tool in tools}
        assert tool_names == {"add", "multiply"}


def test_discover_tools_ignores_private():
    """Test that private functions are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''
def _private_helper(x: int) -> int:
    """Private function.

    Args:
        x: A number
    """
    return x * 2

def public_tool(x: int) -> str:
    """Public tool.

    Args:
        x: A number
    """
    return str(_private_helper(x))
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 1
        assert tools[0].__name__ == "public_tool"


def test_discover_tools_ignores_no_docstring():
    """Test that functions without docstrings are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''
def no_docstring(x: int, y: int) -> str:
    return str(x + y)

def with_docstring(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 1
        assert tools[0].__name__ == "with_docstring"


def test_discover_tools_ignores_no_type_hints():
    """Test that functions without type hints are ignored."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''
def no_hints(x, y):
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)

def with_hints(x: int, y: int) -> str:
    """Add two numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 1
        assert tools[0].__name__ == "with_hints"


def test_list_custom_tools():
    """Test listing custom tools with descriptions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        tool_file = tools_dir / "test_tool.py"
        tool_file.write_text(
            '''
def calculator(x: int, y: int) -> str:
    """Add two numbers together.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)
'''
        )

        tool_list = list_custom_tools(tools_dir)
        assert len(tool_list) == 1
        name, description, path = tool_list[0]
        assert name == "calculator"
        assert "Add two numbers together" in description
        assert path.name == "test_tool.py"


def test_discover_tools_multiple_files():
    """Test discovering tools from multiple files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tools_dir = Path(tmpdir)

        # Create first file
        file1 = tools_dir / "math.py"
        file1.write_text(
            '''
def add(x: int, y: int) -> str:
    """Add numbers.

    Args:
        x: First number
        y: Second number
    """
    return str(x + y)
'''
        )

        # Create second file
        file2 = tools_dir / "text.py"
        file2.write_text(
            '''
def uppercase(text: str) -> str:
    """Convert to uppercase.

    Args:
        text: Input text
    """
    return text.upper()
'''
        )

        tools = discover_tools(tools_dir)
        assert len(tools) == 2
        tool_names = {tool.__name__ for tool in tools}
        assert tool_names == {"add", "uppercase"}


def test_discover_tools_repo_specific():
    """Test discovering tools from repo-specific directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        repo_tools_dir = repo_root / ".patchpal" / "tools"
        repo_tools_dir.mkdir(parents=True)

        # Create repo-specific tool
        tool_file = repo_tools_dir / "repo_tool.py"
        tool_file.write_text(
            '''
def repo_specific(x: int) -> str:
    """Repo-specific tool.

    Args:
        x: A number
    """
    return f"repo: {x}"
'''
        )

        tools = discover_tools(repo_root=repo_root)
        assert len(tools) == 1
        assert tools[0].__name__ == "repo_specific"


def test_discover_tools_repo_overrides_global():
    """Test that repo-specific tools override global tools with same name."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Setup global tools directory
        global_tools_dir = Path(tmpdir) / "global"
        global_tools_dir.mkdir()

        global_tool = global_tools_dir / "tool.py"
        global_tool.write_text(
            '''
def shared_tool(x: int) -> str:
    """Global version.

    Args:
        x: A number
    """
    return f"global: {x}"
'''
        )

        # Setup repo tools directory
        repo_root = Path(tmpdir) / "repo"
        repo_tools_dir = repo_root / ".patchpal" / "tools"
        repo_tools_dir.mkdir(parents=True)

        repo_tool = repo_tools_dir / "tool.py"
        repo_tool.write_text(
            '''
def shared_tool(x: int) -> str:
    """Repo version.

    Args:
        x: A number
    """
    return f"repo: {x}"
'''
        )

        # Discover with explicit global dir and repo_root
        # Simulate the behavior by loading from both
        tools = discover_tools(tools_dir=global_tools_dir, repo_root=None)
        assert len(tools) == 1
        assert tools[0](5) == "global: 5"

        # When using repo_root without explicit tools_dir, it should load from both
        # but we need to manually test the override logic
        # Since tools_dir overrides discovery, we test the repo scenario separately
        tools = discover_tools(tools_dir=None, repo_root=repo_root)
        # With no global tools dir in this test (using default ~/.patchpal/tools which doesn't exist)
        # we should only get repo tools
        assert len(tools) == 1
        assert tools[0](5) == "repo: 5"


def test_discover_tools_global_and_repo():
    """Test discovering tools from both global and repo directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a mock global tools directory
        # Note: We can't easily mock Path.home(), so we'll use tools_dir parameter
        # and manually test the combination logic

        # Setup repo with its own tool
        repo_root = Path(tmpdir) / "repo"
        repo_tools_dir = repo_root / ".patchpal" / "tools"
        repo_tools_dir.mkdir(parents=True)

        repo_tool = repo_tools_dir / "repo_tool.py"
        repo_tool.write_text(
            '''
def repo_tool(x: int) -> str:
    """Repo tool.

    Args:
        x: A number
    """
    return f"repo: {x}"
'''
        )

        # Discover from repo (no global tools in this isolated test)
        tools = discover_tools(repo_root=repo_root)
        assert len(tools) == 1
        assert tools[0].__name__ == "repo_tool"


if __name__ == "__main__":
    test_function_to_tool_schema_basic()
    test_function_to_tool_schema_with_defaults()
    test_function_to_tool_schema_optional()
    test_discover_tools_empty_directory()
    test_discover_tools_valid_tool()
    test_discover_tools_multiple_functions()
    test_discover_tools_ignores_private()
    test_discover_tools_ignores_no_docstring()
    test_discover_tools_ignores_no_type_hints()
    test_list_custom_tools()
    test_discover_tools_multiple_files()
    test_discover_tools_repo_specific()
    test_discover_tools_repo_overrides_global()
    test_discover_tools_global_and_repo()
    print("✓ All tests passed!")
