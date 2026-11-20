"""Tiny agent: a function-calling agent tuned for small context windows.

Based on "You don't need long context" (Belcak et al., 2026,
https://arxiv.org/html/2611.05306v1), which found that frontier
models keep their task accuracy in 8K-48K windows given two practices:

1. Frequent compaction to a structured handoff note (a brief for the work yet to be
   done, not a narrative of the history), instead of carrying conversation history.
2. Selective reading: long inputs stay on disk and are read in small, bounded pieces.

TinyAgent differs from PatchPalAgent in four ways:
- Handoff compaction: the conversation is replaced with the current request plus a
  handoff note, which always shrinks the context however large recent turns were.
- Tool outputs are capped relative to the window size.
- The system prompt adds selective-reading guidance.
- Minimal tools by default (unless enabled_tools is given), since full tool schemas
  alone can fill most of an 8K window.

The CLI uses TinyAgent automatically when the context window is at or below
PATCHPAL_SMALL_CONTEXT_THRESHOLD (default 65,536); PATCHPAL_TINY_MODE=true/false forces it.
"""

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from patchpal.agent.function_calling import PatchPalAgent
from patchpal.config import config

# Tools used when enabled_tools isn't given (same set as PATCHPAL_MINIMAL_TOOLS)
TINY_DEFAULT_TOOLS = ["read_file", "read_lines", "edit_file", "write_file", "run_shell"]
TINY_WEB_TOOLS = ["web_search", "web_fetch"]

# Fraction of the context window a single tool result may use (~3 chars per token)
TOOL_OUTPUT_FRACTION = 0.15

# Typical characters per line of read_lines output for code, including its line-number
# prefix (measured: ~47-53 for patchpal's own source files)
CHARS_PER_CODE_LINE = 50

SELECTIVE_READING_PROMPT = """

## Small context window

You are running with a small context window ({limit:,} tokens). When the context fills up,
the conversation is compacted to your current request plus a handoff note you write.
Read only what you need:

- Each tool result is capped at about {max_chars:,} characters (roughly {max_lines} lines of code);
  longer output is truncated, with a note saying where to continue.
- Locate before reading: use run_shell with grep (e.g., `grep -n "def name" file`), `wc -l`,
  or `head` to find the relevant lines, then read_lines a small range around them.
- Never read whole large files or dump long command output. Filter with grep/head/tail.
- Don't re-read ranges you've already read; rely on your notes instead.
- You can't hold a large file in context. If a request needs more than fits (e.g., "read this
  entire file" or "show me all of X"), don't try to read everything: summarize what matters,
  or ask the user what to focus on."""


class TinyAgent(PatchPalAgent):
    """Function-calling agent tuned for small context windows (<= 64K)."""

    agent_type = "tiny"

    def __init__(
        self,
        model_id: str = "anthropic/claude-sonnet-4-5",
        custom_tools: Optional[List[Callable]] = None,
        enabled_tools: Optional[List[str]] = None,
        litellm_kwargs: Optional[Dict[str, Any]] = None,
    ):
        """Initialize the tiny agent.

        Args:
            model_id: LiteLLM model identifier
            custom_tools: Optional list of Python functions to add as tools
            enabled_tools: Optional list of tool names to enable. Defaults to a minimal set
                          (plus web tools if enabled) unless PATCHPAL_ENABLED_TOOLS is set.
            litellm_kwargs: Optional dict of extra parameters to pass to litellm.completion()
        """
        import os

        if enabled_tools is None and not os.getenv("PATCHPAL_ENABLED_TOOLS"):
            enabled_tools = list(TINY_DEFAULT_TOOLS)
            if config.ENABLE_WEB:
                enabled_tools += TINY_WEB_TOOLS

        super().__init__(
            model_id=model_id,
            custom_tools=custom_tools,
            enabled_tools=enabled_tools,
            litellm_kwargs=litellm_kwargs,
        )

        # The context limit may change after model detection (application inference
        # profiles), so rebuild the window-dependent system prompt now that it's final
        self._refresh_system_prompt()

    @classmethod
    def from_agent(cls, agent: PatchPalAgent) -> "TinyAgent":
        """Convert a freshly created PatchPalAgent into a TinyAgent.

        Reuses the agent's state (including Bedrock model detection, which costs an API
        call), so the CLI can create a normal agent, check its detected context limit, and
        switch without detecting twice.

        Args:
            agent: A PatchPalAgent that hasn't run yet

        Returns:
            A TinyAgent with the same model, tools, and settings
        """
        tiny = cls.__new__(cls)
        tiny.__dict__.update(agent.__dict__)

        # Apply TinyAgent's default tools unless tools were chosen explicitly
        import os

        if agent.enabled_tools is None and not os.getenv("PATCHPAL_ENABLED_TOOLS"):
            tiny.enabled_tools = list(TINY_DEFAULT_TOOLS)
            if config.ENABLE_WEB:
                tiny.enabled_tools += TINY_WEB_TOOLS
        tiny.context_manager.set_tools(tiny._build_tools())
        tiny._refresh_system_prompt()
        return tiny

    # ------------------------------------------------------------------
    # Window-dependent settings
    # ------------------------------------------------------------------

    def _max_tool_output_chars(self) -> int:
        limit = getattr(getattr(self, "context_manager", None), "context_limit", 8192)
        return max(2_000, int(limit * TOOL_OUTPUT_FRACTION * 3))

    def _build_system_prompt(self) -> str:
        base = super()._build_system_prompt()
        if not hasattr(self, "context_manager"):
            # Called before the context manager exists; finalized in _refresh_system_prompt()
            return base
        max_chars = self._max_tool_output_chars()
        return base + SELECTIVE_READING_PROMPT.format(
            limit=self.context_manager.context_limit,
            max_chars=max_chars,
            max_lines=self._max_tool_output_lines_estimate(),
        )

    def _max_tool_output_lines_estimate(self) -> int:
        """Approximate lines of code that fit in one tool result."""
        return max(20, self._max_tool_output_chars() // CHARS_PER_CODE_LINE)

    def _refresh_system_prompt(self) -> None:
        self.system_prompt = self._build_system_prompt()
        self.context_manager.system_prompt = self.system_prompt

    def _tool_output_limits(self):
        max_lines, max_chars = super()._tool_output_limits()
        return max_lines, min(max_chars, self._max_tool_output_chars())

    def _truncation_hint(
        self,
        tool_name: str,
        tool_args: Dict[str, Any],
        truncated_output: str,
        max_lines: int,
        max_chars: int,
    ) -> str:
        """Tell the model exactly where a truncated file read stopped and how to continue.

        A 4B model at 8K otherwise guessed ranges and re-read the same lines repeatedly.
        """
        path = tool_args.get("path")
        if tool_name in ("read_file", "read_lines") and path:
            last_line = self._last_line_shown(tool_name, tool_args, truncated_output)
            if last_line:
                next_start = last_line + 1
                chunk = self._max_tool_output_lines_estimate()
                return (
                    f"[Truncated after line {last_line:,} (limit: ~{max_chars:,} characters). "
                    f"To continue, call read_lines(path={path!r}, start_line={next_start}, "
                    f"end_line={next_start + chunk - 1}). Read only the parts you need.]"
                )
        return (
            f"[Output truncated to ~{max_chars:,} characters. Use run_shell with grep, head, "
            f"or tail to filter, or read_lines for a small range.]"
        )

    @staticmethod
    def _last_line_shown(
        tool_name: str, tool_args: Dict[str, Any], truncated_output: str
    ) -> Optional[int]:
        """Return the last complete file line included in a truncated read, if known."""
        import re

        if tool_name == "read_lines":
            # read_lines prefixes each line with its line number ("  123  text")
            numbers = re.findall(r"^\s*(\d+)  ", truncated_output, flags=re.MULTILINE)
            if len(numbers) >= 2:
                return int(numbers[-2])  # The last one may be cut off mid-line
            try:
                return int(tool_args.get("start_line", 1)) if numbers else None
            except (TypeError, ValueError):
                return None
        # read_file returns raw content: count complete lines
        complete_lines = truncated_output.count("\n")
        return complete_lines if complete_lines > 0 else None

    # ------------------------------------------------------------------
    # Handoff compaction
    # ------------------------------------------------------------------

    def run(self, user_message: str, max_iterations: int = 100) -> str:
        """Run the agent on a user message (resets the per-turn handoff count)."""
        self._handoffs_this_turn = 0
        return super().run(user_message, max_iterations)

    def _should_stop_turn(self) -> Optional[str]:
        """Stop the turn after too many handoffs without a new user message.

        A request that can't fit in the window (e.g., "read this whole file" at 8K) would
        otherwise compact and restart indefinitely. Reply "continue" to keep going.
        """
        limit = config.MAX_HANDOFFS_PER_TURN
        count = getattr(self, "_handoffs_this_turn", 0)
        if limit <= 0 or count < limit:
            return None
        print(
            f"\033[1;33m⚠️  Stopping: {count} compactions this turn without finishing "
            f"(PATCHPAL_MAX_HANDOFFS_PER_TURN={limit}).\033[0m\n"
        )
        return (
            f"I stopped after {count} context compactions in this turn without finishing. "
            f"This request may need more than fits in the {self.context_manager.context_limit:,}-token "
            f"context window (e.g., reading a large file in full).\n\n"
            f"💡 Try a narrower request (e.g., a specific function or question about the file), "
            f"or type 'continue' to keep going. To change this limit, set "
            f"PATCHPAL_MAX_HANDOFFS_PER_TURN (0 = unlimited)."
        )

    def _perform_auto_compaction(self):
        """Compact by replacing the conversation with the request plus a handoff note."""
        return self._perform_handoff_compaction()

    def _save_history_for_handoff(self) -> Optional[str]:
        """Save the full message history to a file before handoff compaction.

        Lets the agent recover details dropped by compaction (e.g., with grep or read_lines).

        Returns:
            Path to the saved file, or None if saving failed
        """
        try:
            from patchpal.tools.common import PATCHPAL_DIR

            history_dir = PATCHPAL_DIR / "history"
            history_dir.mkdir(parents=True, exist_ok=True)
            path = history_dir / f"handoff_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.md"

            lines = []
            for msg in self.messages:
                role = msg.get("role", "?")
                if role == "tool":
                    role = f"tool result ({msg.get('name', '')})"
                lines.append(f"## {role}\n")
                content = msg.get("content")
                if content:
                    lines.append(str(content) + "\n")
                for tc in msg.get("tool_calls") or []:
                    fn = getattr(tc, "function", None)
                    if fn is None and isinstance(tc, dict):
                        fn = tc.get("function", {})
                    name = getattr(fn, "name", None) or (fn or {}).get("name", "")
                    args = getattr(fn, "arguments", None) or (fn or {}).get("arguments", "")
                    lines.append(f"[tool call] {name}({args})\n")
            path.write_text("\n".join(lines), encoding="utf-8")
            return str(path)
        except Exception:
            return None

    def _perform_handoff_compaction(self):
        """Handoff compaction for small context windows.

        Replaces the conversation with [memory, current request + handoff note]. Unlike
        summary compaction (which keeps the last 2 turns), this always shrinks the context,
        however large the recent turns are.
        """
        # Prevent compaction loops: skip only if nothing new since the last compaction
        if (
            self._last_compaction_message_count > 0
            and len(self.messages) <= self._last_compaction_message_count
        ):
            print("\033[2m   Skipping compaction - no new messages since last compact\033[0m")
            return

        memory_messages = [m for m in self.messages if m.get("metadata", {}).get("is_memory")]
        conversation = [m for m in self.messages if not m.get("metadata", {}).get("is_memory")]

        # The current request is the last user message (compaction can run mid-turn).
        # If that's an earlier handoff (second compaction in one long turn), reuse its request.
        last_user = next((m for m in reversed(conversation) if m.get("role") == "user"), None)
        if last_user is None or len(conversation) < 2:
            print("\033[2m   Skipping compaction - nothing to hand off\033[0m")
            return
        if last_user.get("metadata", {}).get("is_handoff"):
            request_text = last_user["metadata"].get("request", "")
        else:
            request_text = last_user.get("content", "")
            if not isinstance(request_text, str):
                request_text = str(request_text)

        # If the turn just finished, keep the final reply so follow-ups like "yes" still make
        # sense and user/assistant roles keep alternating when the next request is added
        final_reply = None
        last_msg = conversation[-1]
        if last_msg.get("role") == "assistant" and not last_msg.get("tool_calls"):
            reply = str(last_msg.get("content") or "")
            max_reply_chars = int(self.context_manager.context_limit * 0.10 * 3)
            if len(reply) > max_reply_chars:
                reply = reply[:max_reply_chars] + "\n\n[... reply truncated during compaction ...]"
            final_reply = {"role": "assistant", "content": reply}

        stats_before = self.context_manager.get_usage_stats(self.messages)
        print(
            f"\n\033[1;33m⚠️  Context window at {stats_before['usage_percent']}% capacity. "
            f"Compacting (handoff)...\033[0m"
        )
        print(
            f"\033[2m   Current: {stats_before['total_tokens']:,} / {stats_before['context_limit']:,} tokens "
            f"(system: {stats_before['system_tokens']:,}, tools: {stats_before.get('tool_tokens', 0):,}, "
            f"messages: {stats_before['message_tokens']:,}, "
            f"output reserve: {stats_before['output_reserve']:,})\033[0m"
        )

        # If the conversation itself overflows the window, the handoff request would fail.
        # Truncate large tool outputs first (the full history is saved below).
        if stats_before["usage_ratio"] >= 1.0:
            pruned = self._prune_tool_outputs_inline(
                max_chars=self._max_tool_output_chars(),
                truncation_message="\n\n[... content truncated due to context window limits ...]",
            )
            if pruned:
                print(f"\033[2m   Truncated ~{pruned:,} chars of large tool outputs first\033[0m")

        history_path = self._save_history_for_handoff()

        # Cap the note so the result is always small: ~10% of the window, within the reserve
        max_note_tokens = max(
            200,
            min(
                self.context_manager.output_reserve, int(self.context_manager.context_limit * 0.10)
            ),
        )

        print("\033[2m   Generating handoff note...\033[0m", flush=True)
        try:
            note = self.context_manager.create_handoff(
                [m for m in self.messages if not m.get("metadata", {}).get("is_memory")],
                self._call_compaction_llm,
                max_note_tokens,
            )
        except Exception as e:
            print(f"\033[1;31m✗ Handoff compaction failed: {e}\033[0m", flush=True)
            # Fall back to truncating tool outputs so the session can continue
            pruned = self._prune_tool_outputs_inline(
                max_chars=max(2_000, int(self.context_manager.context_limit * 0.10 * 3)),
                truncation_message="\n\n[... content truncated during compaction. Use read_lines or grep for targeted access ...]",
            )
            if pruned:
                print(f"\033[2m   Truncated ~{pruned:,} chars of tool outputs instead\033[0m")
            print("\033[1;33m   Consider using '/clear' to start fresh.\033[0m\n")
            self.last_prompt_tokens = None
            return

        from patchpal.tools import common as tools_common

        # State the project directory explicitly: a 4B model at 8K otherwise took the only
        # absolute path in the message (the saved history under ~/.patchpal) for the project
        # root and looked for project files there.
        workdir_line = (
            f"\n\nWorking directory: {tools_common.REPO_ROOT} "
            f"(relative paths in this note are relative to it)"
        )
        history_line = (
            f"\n\nPatchPal's saved log of the pre-compaction conversation (not a project file; "
            f"search it with grep/read_lines only if you need a detail from earlier): {history_path}"
            if history_path
            else ""
        )
        handoff_msg = {
            "role": "user",
            "content": (
                f"Original request (already in progress - continue from the note below; "
                f"don't restart from scratch):\n{request_text}\n\n"
                f"[HANDOFF NOTE - the conversation was compacted to fit the context window. "
                f"Continue from this note.]\n\n{note}{workdir_line}{history_line}"
            ),
            "metadata": {
                "is_handoff": True,
                "request": request_text,
                "original_message_count": len(self.messages),
                "timestamp": datetime.now().isoformat(),
            },
        }
        new_messages = memory_messages + [handoff_msg] + ([final_reply] if final_reply else [])

        new_tokens = self.context_manager.estimator.estimate_messages_tokens(new_messages)
        old_tokens = self.context_manager.estimator.estimate_messages_tokens(self.messages)
        if new_tokens >= old_tokens:
            print(
                "\033[1;33m⚠️  Handoff note isn't smaller than the history - keeping history\033[0m\n"
            )
            return

        self.messages = new_messages
        self.last_prompt_tokens = None  # Pre-compaction count is stale
        self._last_compaction_message_count = len(self.messages)
        self._handoffs_this_turn = getattr(self, "_handoffs_this_turn", 0) + 1

        stats_after = self.context_manager.get_usage_stats(self.messages)
        print(
            f"\033[1;32m✓ Compaction complete. Saved {stats_before['total_tokens'] - stats_after['total_tokens']:,} "
            f"tokens ({stats_before['usage_percent']}% → {stats_after['usage_percent']}%)\033[0m"
        )
        if history_path:
            print(f"\033[2m   Full history saved to {history_path}\033[0m")
        print()


def create_tiny_agent(
    model_id: str = "anthropic/claude-sonnet-4-5",
    custom_tools: Optional[List[Callable]] = None,
    enabled_tools: Optional[List[str]] = None,
    litellm_kwargs: Optional[Dict[str, Any]] = None,
) -> TinyAgent:
    """Create and return a TinyAgent (for small context windows).

    Args:
        model_id: LiteLLM model identifier
        custom_tools: Optional list of Python functions to use as custom tools
        enabled_tools: Optional list of tool names to enable (defaults to a minimal set)
        litellm_kwargs: Optional dict of extra parameters to pass to litellm.completion()

    Returns:
        A TinyAgent instance
    """
    return TinyAgent(
        model_id=model_id,
        custom_tools=custom_tools,
        enabled_tools=enabled_tools,
        litellm_kwargs=litellm_kwargs,
    )


def is_small_context(context_limit: int) -> bool:
    """Whether a context window is small enough to use TinyAgent automatically."""
    threshold = config.SMALL_CONTEXT_THRESHOLD
    return threshold > 0 and context_limit <= threshold


def should_use_tiny_agent(context_limit: int) -> bool:
    """Decide whether to use TinyAgent (PATCHPAL_TINY_MODE overrides the automatic check)."""
    mode = config.TINY_MODE
    if mode is not None:
        return mode
    return is_small_context(context_limit)
