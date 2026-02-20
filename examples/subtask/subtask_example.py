#!/usr/bin/env python3
"""
subtask_example.py - Demonstrate subtask mode with isolated context

This example shows how to use subtask mode for complex sub-problems
that would normally bloat your main conversation context.

Key benefits:
- Fresh context for subtask (not polluted by main conversation)
- Only the result gets injected back to parent
- Ideal for local models with limited context windows
- Perfect for iterative tasks (write tests, fix until passing)

Usage:
    python subtask_example.py
"""

import sys
from pathlib import Path

# Add patchpal to path if running from examples directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from patchpal.agent import create_agent


def main():
    """Demonstrate subtask mode."""

    print("=" * 80)
    print("Subtask Mode Example")
    print("=" * 80)
    print()
    print("This example shows how subtask mode creates isolated context")
    print("for complex sub-problems, keeping your main conversation clean.")
    print()
    print("=" * 80)
    print()

    # Create agent
    agent = create_agent()

    # Simulate a conversation with growing context
    print("Step 1: Main conversation (context builds up)\n")

    agent.run("What files are in the current directory?")
    print("\n")

    agent.run("What's the structure of patchpal/agent.py?")
    print("\n")

    # Now main context has ~50K tokens
    # Instead of adding more to it, use a subtask with fresh context

    print("Step 2: Delegate complex task to subtask with fresh context\n")

    agent.run_subtask(
        task_prompt="""
        Analyze the test coverage in tests/ directory.

        1. List all test files
        2. Count total test functions
        3. Identify any untested modules
        4. Provide a brief summary

        Output <SUBTASK_DONE> when analysis complete.
        """,
        max_iterations=5,
        completion_signal="<SUBTASK_DONE>",
    )

    print("\nStep 3: Continue main conversation (only has the result)\n")

    # Main agent now has subtask result but NOT all the subtask's exploratory work
    agent.run("Based on that analysis, what should I focus on testing next?")

    print("\n" + "=" * 80)
    print("Example Complete!")
    print("=" * 80)
    print()
    print("Notice how:")
    print("• Subtask ran in fresh ~5K token context (not 50K+)")
    print("• Main conversation only got the final analysis (not all the file reads)")
    print("• Parent can continue without context pollution")
    print()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
