"""ReAct agent implementation that doesn't require native function calling.

This agent uses the ReAct (Reason + Act) pattern with text-based tool invocation,
making it compatible with Ollama models and other LLMs that don't support native
function calling. Based on Simon Willison's simple ReAct pattern:
https://til.simonwillison.net/llms/python-react-pattern
"""

import inspect
import json
import logging
import platform
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import litellm
from rich.console import Console
from rich.markdown import Markdown

from patchpal.cli.streaming import stream_completion
from patchpal.config import config
from patchpal.context import ContextManager
from patchpal.tools.definitions import get_tools

# Suppress verbose LiteLLM logging
litellm.suppress_debug_info = True
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("litellm").setLevel(logging.WARNING)

LLM_TIMEOUT = config.LLM_TIMEOUT


def _get_platform_info() -> str:
    """Generate platform-specific guidance."""
    os_name = platform.system()
    if os_name == "Windows":
        return """## Platform: Windows
Commands execute in Windows shell (CMD-compatible commands work in both CMD and PowerShell):
- Use: `dir`, `type`, `copy`, `move`, `del`, `mkdir`, `rmdir`
- Search: `findstr` (grep), `dir /s` (find), `where` (which)
- Path format: Use backslashes `C:\\path\\to\\file.txt`
- Chain commands: `&&` or `&`
"""
    else:
        return f"""## Platform: {os_name} (Unix-like)
When using run_shell, use Unix commands:
- File operations: `ls`, `cat`, `cp`, `mv`, `rm`, `mkdir`, `rmdir`
- Search: `grep`, `find`, `which`
- Path format: Forward slashes `/path/to/file.txt`
- Chain commands with `&&` or `;`
"""


def _get_current_datetime_message() -> str:
    """Generate current date/time message."""
    now = datetime.now()
    return f"# Current Date and Time\nToday is {now.strftime('%A, %B %d, %Y')}. Current time is {now.strftime('%I:%M %p')}."


class ReActAgent:
    """Agent that uses ReAct pattern instead of native function calling."""

    def __init__(
        self,
        model_id: str = "ollama_chat/llama3.2",
        custom_tools: Optional[List[Callable]] = None,
        enabled_tools: Optional[List[str]] = None,
        litellm_kwargs: Optional[Dict[str, Any]] = None,
        custom_instructions: str = "",
    ):
        """Initialize ReAct agent.

        Args:
            model_id: LiteLLM model identifier
            custom_tools: Optional list of custom Python functions to add as tools
            enabled_tools: Optional list of tool names to enable (whitelist)
            litellm_kwargs: Optional dict of extra parameters for litellm.completion()
            custom_instructions: Optional custom instructions to prepend to system prompt
        """
        self.model_id = model_id
        self.litellm_kwargs = litellm_kwargs or {}
        self.messages = []

        # Token and cost tracking
        self.total_llm_calls = 0
        self.cumulative_input_tokens = 0
        self.cumulative_output_tokens = 0
        self.cumulative_cost = 0.0

        # Get tools
        tools_list, tool_functions = get_tools(
            custom_tools=custom_tools,
            enabled_tools=enabled_tools,
        )
        self.tools = tools_list
        self.tool_functions = tool_functions

        # Build system prompt with ReAct pattern
        self.system_prompt = self._build_system_prompt(custom_instructions)

        # Context manager for token estimation
        self.context_manager = ContextManager(model_id=model_id)

        # Load project memory
        self._load_project_memory()

    def _load_project_memory(self):
        """Load project memory file if it exists."""
        from pathlib import Path

        repo_root = Path(".").resolve()
        home = Path.home()
        memory_path = home / ".patchpal" / "repos" / repo_root.name / "MEMORY.md"

        if memory_path.exists():
            try:
                with open(memory_path, "r", encoding="utf-8") as f:
                    memory_content = f.read().strip()
                    if memory_content and not memory_content.startswith(
                        "# Project Memory\n\nThis file"
                    ):
                        # Only add if there's actual content (not just the template)
                        self.messages.append(
                            {
                                "role": "system",
                                "content": f"# Project Memory (MEMORY.md)\n\n{memory_content}",
                            }
                        )
            except Exception:
                pass  # Silently skip if can't read

    def _build_system_prompt(self, custom_instructions: str) -> str:
        """Build the ReAct system prompt with tool descriptions."""

        # Build tool descriptions
        tool_descriptions = []
        for tool in self.tools:
            tool_name = tool["function"]["name"]
            tool_desc = tool["function"].get("description", "")
            params = tool["function"].get("parameters", {}).get("properties", {})

            param_list = []
            for param_name, param_info in params.items():
                param_type = param_info.get("type", "string")
                param_desc = param_info.get("description", "")
                param_list.append(f"  - {param_name} ({param_type}): {param_desc}")

            tool_str = f"**{tool_name}**: {tool_desc}"
            if param_list:
                tool_str += "\n" + "\n".join(param_list)
            tool_descriptions.append(tool_str)

        tools_section = "\n\n".join(tool_descriptions)

        platform_info = _get_platform_info()
        datetime_info = _get_current_datetime_message()

        prompt = f"""You are an expert software engineer assistant that solves tasks step-by-step.

{platform_info}

{datetime_info}

{custom_instructions}

## Available Tools

{tools_section}

## ReAct Pattern

You follow the ReAct (Reason + Act) pattern to solve tasks:

1. **Thought**: Think about what you need to do
2. **Action**: Call a tool using this exact format:
   Action: tool_name: {{"param1": "value1", "param2": "value2"}}
   PAUSE
3. **Observation**: You'll receive the tool's output
4. **Repeat** steps 1-3 as needed, OR
5. **Answer**: Provide your final response when done

## Action Format

When you want to use a tool, output EXACTLY this format:
```
Action: tool_name: {{"param": "value"}}
PAUSE
```

After PAUSE, you'll receive:
```
Observation: <tool output>
```

Then you can either:
- Perform another Action (if you need more information)
- Output an Answer (if you're done)

## Answer Format

When you're ready to give your final response:
```
Answer: <your response>
```

## Example Session

Question: What Python files are in the src directory?
Thought: I need to list files in the src directory.
Action: list_files: {{"path": "src"}}
PAUSE

Observation: file1.py, file2.py, file3.py

Thought: I have the list of files. I can now provide the answer.
Answer: The src directory contains file1.py, file2.py, and file3.py

## Important Guidelines

1. **Answer directly if you can** - If you already know the answer, just output it. Don't use tools unnecessarily.
2. **Use tools for code/files** - Only use tools when you need to read, edit, or analyze code/files.
3. **One action per turn** - Always output "PAUSE" after an Action line.
4. **Stop after answering** - Once you output an Answer, you're done. Don't try to update memory or do additional actions.
5. **Be efficient** - Use read_lines for specific sections, grep for searching.
6. **General knowledge** - For questions about facts, history, geography, etc., just answer directly without web search.

## Examples of Direct Answers

Question: What is the capital of France?
Thought: This is general knowledge, I can answer directly.
Answer: The capital of France is Paris.

Question: How do I fix this error?
Thought: I need to see the error and the code to help. Let me read the file first.
Action: read_file: {{"path": "error.log"}}
PAUSE
"""
        return prompt

    def _calculate_cost(self, response):
        """Calculate cost from response usage data."""
        if not hasattr(response, "usage") or not response.usage:
            return 0.0

        try:
            import litellm

            model_info = litellm.get_model_info(self.model_id)
            input_cost_per_token = model_info.get("input_cost_per_token", 0)
            output_cost_per_token = model_info.get("output_cost_per_token", 0)

            input_tokens = getattr(response.usage, "prompt_tokens", 0)
            output_tokens = getattr(response.usage, "completion_tokens", 0)

            cost = (input_tokens * input_cost_per_token) + (output_tokens * output_cost_per_token)
            return cost
        except Exception:
            return 0.0

    def run(self, user_message: str, max_iterations: int = 100) -> str:
        """Run the agent on a user message.

        Args:
            user_message: The user's question/request
            max_iterations: Maximum number of iterations before giving up

        Returns:
            The agent's final answer
        """
        # Add system prompt as first message if this is the start
        if not self.messages or self.messages[0]["role"] != "system":
            self.messages.insert(0, {"role": "system", "content": self.system_prompt})

        # Add user message
        self.messages.append({"role": "user", "content": user_message})

        # Pattern to match actions
        action_pattern = re.compile(r"^Action:\s*(\w+):\s*(.*)$", re.MULTILINE)

        # Track recent actions to detect loops
        recent_actions = []
        max_recent = 3

        iteration = 0
        while iteration < max_iterations:
            iteration += 1

            # Make LLM call
            enable_streaming = config.STREAM_OUTPUT

            def make_completion_call(stream: bool = False):
                return litellm.completion(
                    model=self.model_id,
                    messages=self.messages,
                    stream=stream,
                    timeout=LLM_TIMEOUT,
                    **self.litellm_kwargs,
                )

            try:
                if enable_streaming:
                    response = stream_completion(make_completion_call, show_progress=True)
                else:
                    response = make_completion_call(stream=False)

                # Track token usage
                self.total_llm_calls += 1
                if hasattr(response, "usage") and response.usage:
                    if hasattr(response.usage, "prompt_tokens"):
                        self.cumulative_input_tokens += response.usage.prompt_tokens
                    if hasattr(response.usage, "completion_tokens"):
                        self.cumulative_output_tokens += response.usage.completion_tokens

                # Track cost
                cost = self._calculate_cost(response)
                self.cumulative_cost += cost

            except Exception as e:
                return f"Error calling model: {e}"

            # Get assistant's response
            result = response.choices[0].message.content or ""

            # Add to messages
            self.messages.append({"role": "assistant", "content": result})

            # Check if this is a final answer (must contain "Answer:" and should be after "Thought:")
            # This indicates the agent is providing its final response
            if "Answer:" in result:
                # Extract the answer part
                answer_parts = result.split("Answer:", 1)
                if len(answer_parts) > 1:
                    answer = answer_parts[1].strip()
                    # Print the thinking part as markdown (before Answer:)
                    thinking_part = answer_parts[0].strip()
                    if thinking_part:
                        console = Console()
                        print()
                        console.print(Markdown(thinking_part))
                        print()

                    # Check if there's also an Action in the response (agent is confused)
                    # If so, ignore the action and just return the answer
                    if "Action:" in result and "PAUSE" in result:
                        # Agent tried to do both - prioritize the answer
                        print("\033[2m⚠️  Agent provided answer and action - using answer\033[0m")

                    return answer
                else:
                    # "Answer:" found but nothing after it - unusual, return full result
                    return result

            # Look for actions
            actions = action_pattern.findall(result)

            if not actions:
                # No action found, but also no answer - print what we got and provide guidance
                console = Console()
                print()
                console.print(Markdown(result))
                print()

                # Provide helpful guidance based on iteration count
                if iteration == 1:
                    # First iteration with no action/answer - encourage direct answer or action
                    self.messages.append(
                        {
                            "role": "user",
                            "content": "Please either:\n1. Output 'Answer: <your answer>' if you can answer directly, OR\n2. Use an Action to gather information",
                        }
                    )
                elif iteration <= 3:
                    # Early iterations - simple prompt
                    self.messages.append(
                        {
                            "role": "user",
                            "content": "Please continue. Either perform an Action or provide an Answer.",
                        }
                    )
                else:
                    # Later iterations - stronger guidance
                    self.messages.append(
                        {
                            "role": "user",
                            "content": "You must either:\n- Perform ONE Action (format: Action: tool_name: {...}\\nPAUSE), OR\n- Provide your final Answer (format: Answer: ...)",
                        }
                    )
                continue

            # Process the first action (only one action per turn)
            tool_name, tool_args_str = actions[0]

            # Check for action loops (same action repeated)
            action_signature = f"{tool_name}:{tool_args_str[:50]}"
            recent_actions.append(action_signature)
            if len(recent_actions) > max_recent:
                recent_actions.pop(0)

            # Detect if we're looping (same action repeated 2+ times recently)
            if len(recent_actions) >= 2 and len(set(recent_actions[-2:])) == 1:
                error_msg = f"Loop detected: {tool_name} called repeatedly with same arguments. Try a different approach or provide an Answer."
                print(f"\033[1;33m⚠️  {error_msg}\033[0m")
                self.messages.append({"role": "user", "content": f"Observation: {error_msg}"})
                continue

            # Print the thinking part before the action
            action_index = result.find("Action:")
            thinking_part = result[:action_index].strip()
            if thinking_part:
                console = Console()
                print()
                console.print(Markdown(thinking_part))
                print()

            # Parse tool arguments
            try:
                tool_args_str = tool_args_str.strip()
                if tool_args_str.startswith("{"):
                    tool_args = json.loads(tool_args_str)
                else:
                    # Handle simple string arguments
                    tool_args = {"query": tool_args_str} if tool_args_str else {}
            except json.JSONDecodeError as e:
                error_msg = f"Error: Invalid JSON in action arguments: {e}"
                print(f"\033[1;31m✗ {error_msg}\033[0m")
                self.messages.append({"role": "user", "content": f"Observation: {error_msg}"})
                continue

            # Get the tool function
            tool_func = self.tool_functions.get(tool_name)
            if tool_func is None:
                error_msg = f"Error: Unknown tool '{tool_name}'"
                print(f"\033[1;31m✗ {error_msg}\033[0m")
                self.messages.append({"role": "user", "content": f"Observation: {error_msg}"})
                continue

            # Show tool call
            print(f"\033[2m🔧 {tool_name}({tool_args})\033[0m", flush=True)

            # Execute the tool
            try:
                # Filter args to only include valid parameters
                sig = inspect.signature(tool_func)
                valid_params = set(sig.parameters.keys())

                # Check for **kwargs
                has_var_keyword = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
                )

                if has_var_keyword:
                    filtered_args = tool_args
                else:
                    filtered_args = {k: v for k, v in tool_args.items() if k in valid_params}

                # Type coercion
                for param_name, param in sig.parameters.items():
                    if param_name in filtered_args:
                        expected_type = param.annotation
                        actual_value = filtered_args[param_name]

                        if expected_type is int and isinstance(actual_value, str):
                            filtered_args[param_name] = int(actual_value)
                        elif expected_type is bool and isinstance(actual_value, str):
                            filtered_args[param_name] = actual_value.lower() in ("true", "1", "yes")

                tool_result = tool_func(**filtered_args)

            except Exception as e:
                tool_result = f"Error executing {tool_name}: {e}"
                print(f"\033[1;31m✗ {tool_name}: {e}\033[0m")

            # Check if operation was cancelled
            if str(tool_result).strip() == "Operation cancelled by user.":
                return "Operation cancelled by user."

            # Apply output limits
            result_str = str(tool_result)
            lines = result_str.split("\n")
            total_lines = len(lines)

            if (
                total_lines > config.MAX_TOOL_OUTPUT_LINES
                or len(result_str) > config.MAX_TOOL_OUTPUT_CHARS
            ):
                truncated_lines = lines[: config.MAX_TOOL_OUTPUT_LINES]
                truncated_str = "\n".join(truncated_lines)

                if len(truncated_str) > config.MAX_TOOL_OUTPUT_CHARS:
                    truncated_str = truncated_str[: config.MAX_TOOL_OUTPUT_CHARS]

                truncation_note = f"\n\n... output truncated ({total_lines:,} total lines) ..."
                result_str = truncated_str + truncation_note

            # Add observation to messages
            observation = f"Observation: {result_str}"
            self.messages.append({"role": "user", "content": observation})

            # Show observation preview
            preview = result_str[:100].replace("\n", " ")
            if len(result_str) > 100:
                preview += "..."
            print(f"\033[2m   → {preview}\033[0m")

        # Max iterations reached
        return (
            f"Maximum iterations ({max_iterations}) reached. Task may be incomplete.\n\n"
            f"Last response: {result}"
        )


def create_react_agent(
    model_id: str = "ollama_chat/llama3.2",
    custom_tools: Optional[List[Callable]] = None,
    enabled_tools: Optional[List[str]] = None,
    litellm_kwargs: Optional[Dict[str, Any]] = None,
    custom_instructions: str = "",
) -> ReActAgent:
    """Create and return a ReAct agent.

    This agent uses text-based tool invocation instead of native function calling,
    making it compatible with models that don't support function calling.

    Args:
        model_id: LiteLLM model identifier (default: ollama_chat/llama3.2)
        custom_tools: Optional list of Python functions to use as custom tools
        enabled_tools: Optional list of tool names to enable (whitelist)
        litellm_kwargs: Optional dict of extra parameters for litellm.completion()
        custom_instructions: Optional custom instructions to prepend to system prompt

    Returns:
        A configured ReActAgent instance

    Example:
        # Basic usage with Ollama
        agent = create_react_agent(model_id="ollama_chat/llama3.2")
        response = agent.run("What files are in the src directory?")

        # With custom tools
        def calculator(x: int, y: int) -> str:
            '''Add two numbers.'''
            return str(x + y)

        agent = create_react_agent(
            model_id="ollama_chat/qwen2.5",
            custom_tools=[calculator]
        )
    """
    from patchpal.tools import reset_session_todos

    reset_session_todos()

    return ReActAgent(
        model_id=model_id,
        custom_tools=custom_tools,
        enabled_tools=enabled_tools,
        litellm_kwargs=litellm_kwargs,
        custom_instructions=custom_instructions,
    )
