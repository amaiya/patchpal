#!/usr/bin/env python3
"""
PatchPal Autopilot Mode - Autonomous iterative development

Implements the "Ralph Wiggum technique", an iterative AI development methodology
where the agent repeatedly works on a task until completion. Named after The Simpsons
character by Geoffrey Huntley, it embodies persistent iteration despite setbacks.

Key Principles:
- Iteration > Perfection: Don't aim for perfect on first try. Let the loop refine the work.
- Failures Are Data: Deterministically bad means failures are predictable and informative.
- Operator Skill Matters: Success depends on writing good prompts, not just having a good model.
- Persistence Wins: Keep trying until success. The loop handles retry logic automatically.

⚠️ SAFETY WARNING:
Autopilot mode disables PatchPal's permission system for autonomous operation.
ONLY use in isolated environments (Docker containers, VMs, throwaway projects).
See examples/ralph/README.md for detailed safety guidelines.

Usage:
    patchpal-autopilot --prompt "Build a REST API with tests"
    patchpal-autopilot --prompt-file task.md --max-iterations 50
"""

import argparse
import os
import sys
import warnings

from patchpal.agent import create_agent
from patchpal.config import config


def autopilot_loop(
    prompt: str,
    completion_promise: str,
    max_iterations: int = 100,
    model: str = None,
    litellm_kwargs: dict = None,
):
    """
    Run autonomous iterative development loop until completion.

    The agent never actually "completes" - every time it tries to return,
    we check for the completion promise. If not found, we feed the same
    prompt back, forcing it to continue working.

    This is the key insight: The agent sees its previous work in the conversation
    history and can adjust its approach, notice what's broken, see failing tests, etc.

    Safety: Autopilot automatically restricts file access to the current directory
    (PATCHPAL_RESTRICT_TO_REPO=true) to prevent PII leakage and limit scope.
    Override with PATCHPAL_RESTRICT_TO_REPO=false if needed.

    Args:
        prompt: Task description for the agent
        completion_promise: String that signals task completion (e.g., "COMPLETE", "DONE")
        max_iterations: Maximum number of autopilot iterations before giving up
        model: Optional model override (defaults to PATCHPAL_MODEL env var)
        litellm_kwargs: Optional dict of extra parameters to pass to litellm.completion()
                       (e.g., {"reasoning_effort": "high"} for reasoning models)

    Returns:
        Agent's final response if completion promise found, None otherwise
    """
    # Disable permissions for autonomous operation
    os.environ["PATCHPAL_REQUIRE_PERMISSION"] = "false"

    # Restrict to current directory for safety (prevent PII leakage, limit scope)
    # This ensures the agent only works within the project directory
    if "PATCHPAL_RESTRICT_TO_REPO" not in os.environ:
        os.environ["PATCHPAL_RESTRICT_TO_REPO"] = "true"

    # Discover custom tools from ~/.patchpal/tools/ and <repo>/.patchpal/tools/
    from pathlib import Path

    from patchpal.tools.tool_schema import discover_tools, list_custom_tools

    repo_root = Path(".").resolve()
    custom_tools = discover_tools(repo_root=repo_root)

    # Create agent
    agent = create_agent(
        model_id=model or config.MODEL,
        custom_tools=custom_tools,
        litellm_kwargs=litellm_kwargs,
    )

    print("=" * 80)
    print("✈️  PatchPal Autopilot Mode Starting")
    print("=" * 80)
    print(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"Completion promise: '{completion_promise}'")
    print(f"Max iterations: {max_iterations}")
    print(f"Model: {agent.model_id}")
    print(f"Working directory: {repo_root}")
    if config.RESTRICT_TO_REPO:
        print("🔒 File access restricted to working directory")

    # Show custom tools info if any were loaded
    custom_tool_info = list_custom_tools(repo_root=repo_root)
    if custom_tool_info:
        tool_names = [name for name, _, _ in custom_tool_info]
        tools_str = ", ".join(tool_names)
        print(f"🔧 Custom tools: {tools_str}")

    print("=" * 80)
    print()

    for iteration in range(max_iterations):
        print(f"\n{'=' * 80}")
        print(f"🔄 Autopilot Iteration {iteration + 1}/{max_iterations}")
        print(f"{'=' * 80}\n")

        # Run agent with the SAME prompt every time
        # The agent's conversation history accumulates, so it can see all previous work
        response = agent.run(prompt, max_iterations=100)

        print(f"\n{'=' * 80}")
        print("📝 Agent Response:")
        print(f"{'=' * 80}")
        print(response)
        print(f"{'=' * 80}\n")

        # Show cumulative cost tracking after each iteration
        print(f"💰 Cumulative Cost (after iteration {iteration + 1}):")
        print(f"   Total LLM calls: {agent.total_llm_calls}")
        print(
            f"   Total tokens: {agent.cumulative_input_tokens + agent.cumulative_output_tokens:,}"
        )
        if agent.cumulative_cost > 0:
            print(f"   Total cost: ${agent.cumulative_cost:.4f}")
        print()

        # Check for completion promise
        if completion_promise in response:
            print(f"\n{'=' * 80}")
            print(f"✅ COMPLETION DETECTED after {iteration + 1} iterations!")
            print(f"{'=' * 80}\n")
            print("Agent found completion promise in response.")
            print(f"Total LLM calls: {agent.total_llm_calls}")
            print(
                f"Total tokens: {agent.cumulative_input_tokens + agent.cumulative_output_tokens:,}"
            )
            if agent.cumulative_cost > 0:
                print(f"Total cost: ${agent.cumulative_cost:.4f}")
            return response

        # Stop hook: Agent tried to complete, but no completion promise
        # Feed the same prompt back - agent will see its previous work in history
        print("\n⚠️  No completion promise detected. Continuing...")
        print(f"   (Messages in history: {len(agent.messages)})")

        # Show context usage
        stats = agent.context_manager.get_usage_stats(agent.messages)
        print(f"   (Context usage: {stats['usage_percent']}%)")

    # Max iterations reached without completion
    print(f"\n{'=' * 80}")
    print(f"⚠️  MAX ITERATIONS REACHED ({max_iterations})")
    print(f"{'=' * 80}\n")
    print("Task may be incomplete. Check the agent's work and consider:")
    print("  - Increasing max iterations")
    print("  - Refining the prompt with more specific completion criteria")
    print("  - Breaking the task into smaller phases")
    print(f"\nTotal LLM calls: {agent.total_llm_calls}")
    print(f"Total tokens: {agent.cumulative_input_tokens + agent.cumulative_output_tokens:,}")
    if agent.cumulative_cost > 0:
        print(f"Total cost: ${agent.cumulative_cost:.4f}")

    return None


def main():
    """Autopilot mode CLI entry point."""

    # Suppress warnings to keep CLI clean (e.g., Pydantic, deprecation warnings from dependencies)
    warnings.simplefilter("ignore")

    # Set up argument parser FIRST so --help works before confirmation prompt
    parser = argparse.ArgumentParser(
        description="PatchPal Autopilot - Autonomous iterative development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build a calculator with tests
  patchpal-autopilot --prompt "Create calculator.py with add, subtract, multiply, divide functions. Create test_calculator.py with pytest tests. Run tests to verify." --max-iterations 20

  # Refactor code with specific completion criteria
  patchpal-autopilot --model openai/gpt-5-mini --prompt "Refactor auth.py to use async/await. Update all tests. Run tests to verify."

  # Use prompt from file
  patchpal-autopilot --prompt-file task.md --max-iterations 50

  # With local Ollama model (zero API cost)
  patchpal-autopilot --model ollama_chat/qwen2.5-coder:7b --prompt "..."

  # Custom completion promise (optional, defaults to "COMPLETE")
  patchpal-autopilot --prompt-file task.md --completion-promise "DONE"

  # Skip confirmation prompt (for automation/scripts)
  PATCHPAL_AUTOPILOT_CONFIRMED=true patchpal-autopilot --prompt-file task.md

Prompt Best Practices:
  - Include the completion promise in your prompt (agent sees this as the goal)
  - Clear completion criteria (specific tests, checks, deliverables)
  - Incremental goals (break into phases if complex)
  - Self-correction patterns (run tests, debug, fix, repeat)
  - Example: "Create X. Test X. Fix any errors. Output <promise>COMPLETE</promise>"

Safety:
  - File access restricted to current directory (PATCHPAL_RESTRICT_TO_REPO=true)
  - Permissions disabled for autonomous operation
  - Recommended: Run in containers or throwaway projects
  - See examples/ralph/README.md for detailed safety guidelines

Related Resources (Ralph Wiggum Technique):
  - https://www.humanlayer.dev/blog/brief-history-of-ralph
  - https://awesomeclaude.ai/ralph-wiggum
  - https://github.com/ghuntley/ralph
        """,
    )
    parser.add_argument("--prompt", type=str, help="Task prompt (or use --prompt-file)")
    parser.add_argument("--prompt-file", type=str, help="Path to file containing prompt")
    parser.add_argument(
        "--completion-promise",
        type=str,
        default="COMPLETE",
        help='String that signals completion (default: "COMPLETE")',
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="Maximum autopilot iterations (default: 50)",
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model to use (overrides PATCHPAL_MODEL env var)",
    )

    args = parser.parse_args()

    # Show safety warning only if not already confirmed (after argparse so --help works)
    if not config.AUTOPILOT_CONFIRMED:
        print("\n" + "⚠️" * 40)
        print("  PATCHPAL AUTOPILOT MODE - AUTONOMOUS OPERATION")
        print("⚠️" * 40)
        print()
        print("Autopilot disables PatchPal's permission system for autonomous operation.")
        print()
        print("🔒 RECOMMENDED: Run in isolated environments:")
        print("   • Docker/Podman containers (e.g., use patchpal-sandbox if you're not already)")
        print("   • Dedicated VMs or test machines")
        print()
        print("❌ DO NOT RUN on production systems.")
        print()
        print("This implements the 'Ralph Wiggum technique' - see examples/ralph/README.md")
        print()

    # Check for environment variable to skip prompt (for automation)
    if not config.AUTOPILOT_CONFIRMED:
        try:
            response = input("Continue with autopilot mode? (yes/no): ").strip().lower()
            if response != "yes":
                print("\nAborted.")
                sys.exit(1)
        except (EOFError, KeyboardInterrupt):
            print("\n\nAborted.")
            sys.exit(1)

    print()

    # Get prompt from file or argument
    if args.prompt_file:
        try:
            with open(
                args.prompt_file, "r", encoding="utf-8", errors="surrogateescape", newline=None
            ) as f:
                prompt = f.read()
        except FileNotFoundError:
            print(f"❌ Error: Prompt file not found: {args.prompt_file}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error reading prompt file: {e}")
            sys.exit(1)
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("Either --prompt or --prompt-file is required")

    # Auto-append completion instruction if not already present
    completion_tag = f"<promise>{args.completion_promise}</promise>"
    if completion_tag not in prompt:
        prompt = (
            f"{prompt}\n\n"
            f"When you have successfully completed the task, output the following exactly:\n"
            f"{completion_tag}"
        )

    # Run autopilot loop
    try:
        result = autopilot_loop(
            prompt=prompt,
            completion_promise=args.completion_promise,
            max_iterations=args.max_iterations,
            model=args.model,
        )

        if result:
            print("\n✅ Autopilot completed successfully!")
            sys.exit(0)
        else:
            print("\n⚠️  Autopilot did not complete within max iterations")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Autopilot interrupted by user (Ctrl-C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
