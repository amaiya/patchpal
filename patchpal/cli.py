import os
import sys
from patchpal.agent import create_agent


def main():
    """Main CLI entry point for PatchPal."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("Error: ANTHROPIC_API_KEY environment variable not set.")
        print("\nTo fix this:")
        print("1. Get your API key from https://console.anthropic.com/")
        print("2. Set it in your environment:")
        print("   export ANTHROPIC_API_KEY=your_api_key_here")
        print("\nOr create a .env file with:")
        print("   ANTHROPIC_API_KEY=your_api_key_here")
        sys.exit(1)

    # Create the agent
    agent = create_agent()

    print("=" * 80)
    print("PatchPal - Claude Code Clone")
    print("=" * 80)
    print("\nType 'exit' or 'quit' to exit the program.\n")

    while True:
        try:
            # Get user input
            user_input = input("\n\033[1;36mYou:\033[0m ").strip()

            # Check for exit commands
            if user_input.lower() in ['exit', 'quit', 'q']:
                print("\nGoodbye!")
                break

            # Skip empty input
            if not user_input:
                continue

            # Run the agent
            print()  # Add blank line before agent output
            result = agent.run(user_input)

            print("\n" + "=" * 80)
            print("\033[1;32mAgent:\033[0m", result)
            print("=" * 80)

        except KeyboardInterrupt:
            print("\n\nInterrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n\033[1;31mError:\033[0m {e}")
            print("Please try again or type 'exit' to quit.")


if __name__ == "__main__":
    main()
