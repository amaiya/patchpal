#!/usr/bin/env python3
"""
ralph.py - True Ralph Wiggum technique for PatchPal

The Ralph Wiggum technique is an iterative AI development methodology where
the agent repeatedly works on a task until completion. Named after The Simpsons
character, it embodies the philosophy of persistent iteration despite setbacks.

Key Principles:
- Iteration > Perfection: Don't aim for perfect on first try. Let the loop refine the work.
- Failures Are Data: Deterministically bad means failures are predictable and informative.
- Operator Skill Matters: Success depends on writing good prompts, not just having a good model.
- Persistence Wins: Keep trying until success. The loop handles retry logic automatically.

Usage:
    python ralph.py --prompt "Build a REST API with tests" --completion-promise "COMPLETE" --max-iterations 50
    python ralph.py --prompt-file PROMPT.md --completion-promise "DONE" --max-iterations 30
"""

import argparse
import os
import sys
from pathlib import Path

# Add patchpal to path if running from examples directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from patchpal.agent import create_agent


def ralph_loop(prompt: str, completion_promise: str, max_iterations: int = 100, model: str = None):
    """
    Implements the Ralph Wiggum technique with a proper stop hook.

    The agent never actually "completes" - every time it tries to return,
    we check for the completion promise. If not found, we feed the same
    prompt back, forcing it to continue working.

    This is the key insight: The agent sees its previous work in the conversation
    history and can adjust its approach, notice what's broken, see failing tests, etc.

    Args:
        prompt: Task description for the agent
        completion_promise: String that signals task completion (e.g., "COMPLETE", "DONE")
        max_iterations: Maximum number of Ralph iterations before giving up
        model: Optional model override (defaults to PATCHPAL_MODEL env var)

    Returns:
        Agent's final response if completion promise found, None otherwise
    """
    # Disable permissions for autonomous operation
    os.environ["PATCHPAL_REQUIRE_PERMISSION"] = "false"

    # Create agent
    agent = create_agent(
        model_id=model or os.getenv("PATCHPAL_MODEL", "anthropic/claude-sonnet-4-5")
    )

    print("=" * 80)
    print("🎭 Ralph Wiggum Loop Starting")
    print("=" * 80)
    print(f"Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"Completion promise: '{completion_promise}'")
    print(f"Max iterations: {max_iterations}")
    print(f"Model: {agent.model_id}")
    print("=" * 80)
    print()

    for iteration in range(max_iterations):
        print(f"\n{'=' * 80}")
        print(f"🔄 Ralph Iteration {iteration + 1}/{max_iterations}")
        print(f"{'=' * 80}\n")

        # Run agent with the SAME prompt every time
        # The agent's conversation history accumulates, so it can see all previous work
        response = agent.run(prompt, max_iterations=100)

        print(f"\n{'=' * 80}")
        print("📝 Agent Response:")
        print(f"{'=' * 80}")
        print(response)
        print(f"{'=' * 80}\n")

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
    parser = argparse.ArgumentParser(
        description="Ralph Wiggum loop for PatchPal",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python ralph.py --prompt "Build a REST API with tests" --completion-promise "COMPLETE" --max-iterations 30
  python ralph.py --prompt-file PROMPT.md --completion-promise "DONE" --max-iterations 50

  # With local model (zero API cost)
  python ralph.py --model hosted_vllm/openai/gpt-oss-20b --prompt "..." --completion-promise "COMPLETE"

Prompt Best Practices:
  - Clear completion criteria (specific tests, checks, deliverables)
  - Incremental goals (break into phases)
  - Self-correction patterns (run tests, debug, fix, repeat)
  - Escape hatches (document blocking issues after N failures)
  - Output the completion promise when done: "Output: <promise>COMPLETE</promise>"

Related Resources:
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
        required=True,
        help='String that signals completion (e.g., "COMPLETE", "DONE")',
    )
    parser.add_argument(
        "--max-iterations", type=int, default=50, help="Maximum Ralph iterations (default: 50)"
    )
    parser.add_argument(
        "--model",
        type=str,
        help="Model to use (default: PATCHPAL_MODEL env var or claude-sonnet-4-5)",
    )

    args = parser.parse_args()

    # Get prompt from file or argument
    if args.prompt_file:
        with open(args.prompt_file, "r") as f:
            prompt = f.read()
    elif args.prompt:
        prompt = args.prompt
    else:
        parser.error("Either --prompt or --prompt-file is required")

    # Run Ralph loop
    try:
        result = ralph_loop(
            prompt=prompt,
            completion_promise=args.completion_promise,
            max_iterations=args.max_iterations,
            model=args.model,
        )

        if result:
            print("\n✅ Ralph completed successfully!")
            sys.exit(0)
        else:
            print("\n⚠️  Ralph did not complete within max iterations")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n⚠️  Ralph interrupted by user (Ctrl-C)")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
