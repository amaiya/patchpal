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
        self.last_message_cost = 0.0

        # Track cache-related tokens (for Anthropic/Bedrock models with prompt caching)
        self.cumulative_cache_creation_tokens = 0
        self.cumulative_cache_read_tokens = 0

        # Track OpenAI cache tokens (prompt_tokens_details.cached_tokens)
        self.cumulative_openai_cached_tokens = 0

        # Get built-in tools
        tools_list, tool_functions = get_tools(web_tools_enabled=config.ENABLE_WEB)

        # Filter tools if enabled_tools is specified
        if enabled_tools is not None:
            tools_list = [t for t in tools_list if t["function"]["name"] in enabled_tools]
            tool_functions = {k: v for k, v in tool_functions.items() if k in enabled_tools}

        # Add custom tools
        if custom_tools:
            from patchpal.tools.tool_schema import function_to_tool_schema

            for func in custom_tools:
                tools_list.append(function_to_tool_schema(func))
                tool_functions[func.__name__] = func

        self.tools = tools_list
        self.tool_functions = tool_functions

        # Build system prompt with ReAct pattern
        self.system_prompt = self._build_system_prompt(custom_instructions)

        # Context manager for token estimation
        self.context_manager = ContextManager(model_id=model_id, system_prompt=self.system_prompt)

        # Check if auto-compaction is enabled (default: True)
        self.enable_auto_compact = not config.DISABLE_AUTOCOMPACT

        # Track last compaction to prevent compaction loops
        self._last_compaction_message_count = 0

        # Initialize image handler for vision model support
        from patchpal.tools.image_handler import ImageHandler

        self.image_handler = ImageHandler(self.model_id)

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
        from pathlib import Path

        # Load the ReAct prompt template
        prompt_file = Path(__file__).parent.parent / "prompts" / "react_prompt.md"
        with open(prompt_file, "r", encoding="utf-8") as f:
            template = f.read()

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

        # Fill in the template
        prompt = template.format(
            platform_info=platform_info,
            datetime_info=datetime_info,
            custom_instructions=custom_instructions,
            tools_section=tools_section,
        )

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

    def _prune_tool_outputs_inline(self, max_chars: int, truncation_message: str) -> int:
        """Truncate large tool outputs inline.

        Args:
            max_chars: Maximum characters to keep per output
            truncation_message: Message to append after truncation

        Returns:
            Number of characters pruned
        """
        pruned_chars = 0
        for msg in self.messages:
            if msg.get("role") == "user" and msg.get("content"):
                content = msg["content"]

                # Only prune observations (starts with "Observation:")
                if not content.startswith("Observation:"):
                    continue

                # Skip multimodal content containing images
                if self.image_handler.should_skip_pruning(content):
                    continue

                content_size = len(str(content))
                if content_size > max_chars:
                    original_size = content_size
                    msg["content"] = str(content)[:max_chars] + truncation_message
                    pruned_chars += original_size - len(msg["content"])
        return pruned_chars

    def _is_openai_model(self) -> bool:
        """Check if the current model is an OpenAI model."""
        model_lower = self.model_id.lower()
        return (
            "openai" in model_lower or "gpt" in model_lower or self.model_id.startswith("openai/")
        )

    def _perform_auto_compaction(self):
        """Perform automatic context window compaction using sliding window.

        For ReAct agents (typically small local models), we use a simple sliding
        window approach: keep system prompt + last N messages. This is more
        reliable than LLM-based summarization for smaller models.
        """
        stats_before = self.context_manager.get_usage_stats(self.messages)

        print(
            f"\n\033[1;33m⚠️  Context window at {stats_before['usage_percent']}% capacity. Compacting...\033[0m"
        )

        # Keep system message + last N conversation messages
        # Adjust N based on context size (more for larger contexts)
        context_limit = stats_before["context_limit"]
        if context_limit >= 32000:
            keep_last = 20  # ~32K+ context
        elif context_limit >= 8000:
            keep_last = 12  # 8K-32K context
        else:
            keep_last = 8  # Small context (4K-8K)

        # Find system message (first message)
        system_msg = None
        conversation_msgs = []

        for msg in self.messages:
            if msg.get("role") == "system":
                system_msg = msg
            else:
                conversation_msgs.append(msg)

        # Keep last N conversation messages
        if len(conversation_msgs) > keep_last:
            kept_msgs = conversation_msgs[-keep_last:]
            messages_dropped = len(conversation_msgs) - keep_last

            # Rebuild message list
            if system_msg:
                self.messages = [system_msg] + kept_msgs
            else:
                self.messages = kept_msgs

            stats_after = self.context_manager.get_usage_stats(self.messages)
            print(
                f"\033[1;32m✓ Dropped {messages_dropped} old messages. "
                f"Context: {stats_before['usage_percent']}% → {stats_after['usage_percent']}%\033[0m\n"
            )
        else:
            # Not many messages - try pruning large outputs instead
            print(
                "\033[2m   Not enough messages to drop. Pruning large outputs...\033[0m", flush=True
            )

            pruned_chars = self._prune_tool_outputs_inline(
                max_chars=5_000,
                truncation_message="\n\n[... truncated ...]",
            )

            if pruned_chars > 0:
                stats_after = self.context_manager.get_usage_stats(self.messages)
                print(
                    f"\033[1;32m✓ Pruned {pruned_chars:,} chars. "
                    f"Context: {stats_before['usage_percent']}% → {stats_after['usage_percent']}%\033[0m\n"
                )
            else:
                print(
                    "\033[1;33m⚠️  Unable to reduce context. Consider '/clear' to start fresh.\033[0m\n"
                )

        # Update tracker
        self._last_compaction_message_count = len(self.messages)

    def _cleanup_interrupted_state(self):
        """Clean up state after KeyboardInterrupt during agent execution."""
        # For ReAct agent, no special cleanup needed
        pass

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

            # Look for actions FIRST (before checking for Answer)
            # This ensures we execute tools even if the model hallucinates an answer
            actions = action_pattern.findall(result)

            if not actions:
                # No action found - check if there's an answer instead
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
                        return answer
                    else:
                        # "Answer:" found but nothing after it - unusual, return full result
                        return result

                # No action and no answer - print what we got and provide guidance
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

            # Warn if model also provided an Answer (hallucination/confusion)
            # We'll execute the action anyway since the model explicitly requested it
            if "Answer:" in result:
                print(
                    "\033[2m⚠️  Agent provided both action and answer - executing action first\033[0m"
                )

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
