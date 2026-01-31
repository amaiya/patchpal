"""Utility to automatically convert Python functions to LiteLLM tool schemas.

Also provides custom tools discovery system for loading user-defined tools
from ~/.patchpal/tools/
"""

import inspect
import sys
from importlib import util
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union, get_args, get_origin, get_type_hints


def python_type_to_json_schema(py_type: Any) -> Dict[str, Any]:
    """Convert Python type hint to JSON schema type.

    Args:
        py_type: Python type hint

    Returns:
        JSON schema type dict
    """
    if py_type is type(None):
        return {"type": "null"}

    origin = get_origin(py_type)

    # Handle Optional/Union types
    if origin is Union:
        args = get_args(py_type)
        non_none = [a for a in args if a is not type(None)]
        if non_none:
            return python_type_to_json_schema(non_none[0])

    # Handle List
    if origin is list:
        args = get_args(py_type)
        if args:
            return {"type": "array", "items": python_type_to_json_schema(args[0])}
        return {"type": "array"}

    # Handle Dict
    if origin is dict:
        return {"type": "object"}

    # Basic types
    type_map = {
        str: {"type": "string"},
        int: {"type": "integer"},
        float: {"type": "number"},
        bool: {"type": "boolean"},
        list: {"type": "array"},
        dict: {"type": "object"},
    }

    return type_map.get(py_type, {"type": "string"})


def parse_docstring_params(docstring: str) -> Dict[str, str]:
    """Parse parameter descriptions from Google-style docstring.

    Args:
        docstring: Function docstring

    Returns:
        Dict mapping parameter names to descriptions
    """
    if not docstring:
        return {}

    params = {}
    lines = docstring.split("\n")
    in_args = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        if stripped.lower() in ("args:", "arguments:", "parameters:"):
            in_args = True
            continue

        if in_args:
            # Check if we left the Args section
            if stripped and not line.startswith((" ", "\t")) and ":" in stripped:
                break

            # Parse "param_name: description"
            if ":" in stripped:
                parts = stripped.split(":", 1)
                param_name = parts[0].strip()
                description = parts[1].strip()

                # Collect continuation lines
                for j in range(i + 1, len(lines)):
                    next_line = lines[j].strip()
                    if not next_line or ":" in next_line:
                        break
                    description += " " + next_line

                params[param_name] = description

    return params


def function_to_tool_schema(func: Callable) -> Dict[str, Any]:
    """Convert a Python function to LiteLLM tool schema.

    Extracts schema from function signature and docstring.

    Args:
        func: Python function with type hints and docstring

    Returns:
        LiteLLM tool schema dict
    """
    sig = inspect.signature(func)
    docstring = inspect.getdoc(func) or ""

    # Extract description (first paragraph)
    description = (
        docstring.split("\n\n")[0].replace("\n", " ").strip() or f"Execute {func.__name__}"
    )

    # Parse parameter descriptions
    param_descriptions = parse_docstring_params(docstring)

    # Get type hints
    try:
        type_hints = get_type_hints(func)
    except Exception:
        type_hints = {}

    # Build parameters
    properties = {}
    required = []

    for param_name, param in sig.parameters.items():
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue

        param_type = type_hints.get(param_name, str)
        param_schema = python_type_to_json_schema(param_type)
        param_schema["description"] = param_descriptions.get(param_name, f"Parameter {param_name}")

        properties[param_name] = param_schema

        if param.default is inspect.Parameter.empty:
            required.append(param_name)

    return {
        "type": "function",
        "function": {
            "name": func.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def _is_valid_tool_function(func: Callable) -> bool:
    """Check if a function is valid for use as a tool.

    Args:
        func: Function to validate

    Returns:
        True if function can be used as a tool
    """
    # Must have a docstring
    if not func.__doc__:
        return False

    # Must have type hints
    try:
        sig = inspect.signature(func)
        for param_name, param in sig.parameters.items():
            # Skip *args, **kwargs
            if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
                continue
            # Check if parameter has annotation
            if param.annotation is inspect.Parameter.empty:
                return False
    except Exception:
        return False

    return True


def discover_tools(tools_dir: Optional[Path] = None) -> List[Callable]:
    """Discover custom tool functions from Python files.

    Loads all .py files from the tools directory and extracts functions
    that have proper type hints and docstrings.

    Tool functions must:
    - Have type hints for all parameters
    - Have a docstring with description and Args section
    - Be defined at module level (not nested)
    - Not start with underscore (private functions ignored)

    Args:
        tools_dir: Directory to search for tool files (default: ~/.patchpal/tools/)

    Returns:
        List of callable tool functions
    """
    if tools_dir is None:
        tools_dir = Path.home() / ".patchpal" / "tools"

    if not tools_dir.exists():
        return []

    tools = []
    loaded_modules = []

    # Discover all .py files
    for tool_file in sorted(tools_dir.glob("*.py")):
        try:
            # Create a unique module name to avoid conflicts
            module_name = f"patchpal_custom_tools.{tool_file.stem}"

            # Load the module
            spec = util.spec_from_file_location(module_name, tool_file)
            if spec and spec.loader:
                module = util.module_from_spec(spec)

                # Store reference to prevent garbage collection
                sys.modules[module_name] = module
                loaded_modules.append(module)

                # Execute the module
                spec.loader.exec_module(module)

                # Extract valid tool functions
                for name, obj in inspect.getmembers(module, inspect.isfunction):
                    # Skip private functions
                    if name.startswith("_"):
                        continue

                    # Skip functions from imports (only module-level definitions)
                    if obj.__module__ != module_name:
                        continue

                    # Validate tool function
                    if _is_valid_tool_function(obj):
                        tools.append(obj)

        except Exception as e:
            # Print warning but continue with other tools
            print(
                f"\033[1;33m⚠️  Warning: Failed to load custom tool from {tool_file.name}: {e}\033[0m"
            )
            continue

    return tools


def list_custom_tools(tools_dir: Optional[Path] = None) -> List[tuple[str, str, Path]]:
    """List all custom tools with their descriptions.

    Args:
        tools_dir: Directory to search for tool files (default: ~/.patchpal/tools/)

    Returns:
        List of (tool_name, description, file_path) tuples
    """
    tools = discover_tools(tools_dir)

    result = []
    for tool in tools:
        # Extract description from docstring (first line)
        description = ""
        if tool.__doc__:
            description = tool.__doc__.split("\n")[0].strip()

        # Get source file
        try:
            source_file = Path(inspect.getfile(tool))
        except Exception:
            source_file = Path("unknown")

        result.append((tool.__name__, description, source_file))

    return result
