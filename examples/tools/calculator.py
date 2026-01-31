"""Example custom tools for PatchPal.

This file demonstrates how to create custom tools that extend PatchPal's
capabilities. Tools are automatically discovered from ~/.patchpal/tools/

Requirements for tool functions:
- Type hints for all parameters
- Docstring with description and Args section
- Module-level functions (not nested)
- Return type should typically be str (for LLM consumption)
"""


def add(x: int, y: int) -> str:
    """Add two numbers together.

    Args:
        x: First number
        y: Second number

    Returns:
        The sum as a string
    """
    result = x + y
    return f"{x} + {y} = {result}"


def subtract(x: int, y: int) -> str:
    """Subtract two numbers.

    Args:
        x: First number
        y: Second number (subtracted from x)

    Returns:
        The difference as a string
    """
    result = x - y
    return f"{x} - {y} = {result}"


def multiply(x: float, y: float) -> str:
    """Multiply two numbers.

    Args:
        x: First number
        y: Second number

    Returns:
        The product as a string
    """
    result = x * y
    return f"{x} × {y} = {result}"


def divide(x: float, y: float) -> str:
    """Divide two numbers.

    Args:
        x: Numerator
        y: Denominator

    Returns:
        The quotient as a string
    """
    if y == 0:
        return "Error: Cannot divide by zero"
    result = x / y
    return f"{x} ÷ {y} = {result}"


def calculate_percentage(value: float, percentage: float) -> str:
    """Calculate a percentage of a value.

    Args:
        value: The base value
        percentage: The percentage to calculate (e.g., 20 for 20%)

    Returns:
        The calculated percentage as a string
    """
    result = (value * percentage) / 100
    return f"{percentage}% of {value} = {result}"


def fahrenheit_to_celsius(fahrenheit: float) -> str:
    """Convert Fahrenheit to Celsius.

    Args:
        fahrenheit: Temperature in Fahrenheit

    Returns:
        Temperature in Celsius as a string
    """
    celsius = (fahrenheit - 32) * 5 / 9
    return f"{fahrenheit}°F = {celsius:.2f}°C"


def celsius_to_fahrenheit(celsius: float) -> str:
    """Convert Celsius to Fahrenheit.

    Args:
        celsius: Temperature in Celsius

    Returns:
        Temperature in Fahrenheit as a string
    """
    fahrenheit = (celsius * 9 / 5) + 32
    return f"{celsius}°C = {fahrenheit:.2f}°F"
