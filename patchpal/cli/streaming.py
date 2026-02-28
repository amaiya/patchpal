"""
Streaming renderer for LLM responses with spinner and token counting.

Provides visual feedback during LLM API calls to show that generation is active.
Inspired by kon's streaming implementation.
"""

import threading
import time
from typing import Optional


class StreamRenderer:
    """
    Renders streaming LLM responses with a spinner and token counter.

    Features:
    - Animated spinner to show activity
    - Real-time token counter (appears after threshold)
    - Time tracking for slow responses
    - Interrupt hint

    Example:
        renderer = StreamRenderer()
        renderer.start()

        for chunk in stream:
            renderer.update_tokens(token_count)
            # Process chunk...

        renderer.stop()
    """

    # Spinner frames (Unicode spinning animation)
    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    # Configuration
    UPDATE_INTERVAL = 0.15  # Update spinner every 150ms
    TOKEN_DISPLAY_THRESHOLD = 20  # Show token count after this many tokens
    SLOW_RESPONSE_THRESHOLD = 5.0  # Mark as "slow" after 5 seconds

    def __init__(self, show_tokens: bool = True, show_interrupt_hint: bool = True):
        """
        Initialize the stream renderer.

        Args:
            show_tokens: Whether to show token counter
            show_interrupt_hint: Whether to show Ctrl+C interrupt hint
        """
        self.show_tokens = show_tokens
        self.show_interrupt_hint = show_interrupt_hint

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._token_count = 0
        self._start_time = 0.0
        self._first_token_time: Optional[float] = None
        self._spinner_index = 0
        self._last_output = ""

    def start(self):
        """Start the streaming renderer."""
        if self._running:
            return

        self._running = True
        self._start_time = time.time()
        self._first_token_time = None
        self._token_count = 0
        self._spinner_index = 0

        # Start background thread for spinner animation
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self, show_summary: bool = False):
        """
        Stop the streaming renderer.

        Args:
            show_summary: Whether to show a completion summary
        """
        if not self._running:
            return

        self._running = False

        # Wait for thread to finish
        if self._thread:
            self._thread.join(timeout=0.5)
            self._thread = None

        # Clear the line
        self._clear_line()

        # Optionally show summary
        if show_summary and self._token_count > 0:
            elapsed = time.time() - self._start_time
            print(
                f"\033[2m✓ Generated {self._token_count} tokens in {elapsed:.1f}s\033[0m",
                flush=True,
            )

    def update_tokens(self, token_count: int):
        """
        Update the token counter.

        Args:
            token_count: Current total token count
        """
        self._token_count = token_count

        # Record first token time
        if self._first_token_time is None and token_count > 0:
            self._first_token_time = time.time()

    def _render_loop(self):
        """Background thread that updates the spinner."""
        while self._running:
            self._render()
            time.sleep(self.UPDATE_INTERVAL)

    def _render(self):
        """Render the current status line."""
        # Build status message
        spinner = self.SPINNER_FRAMES[self._spinner_index]
        self._spinner_index = (self._spinner_index + 1) % len(self.SPINNER_FRAMES)

        # Base message with spinner
        parts = [f"\033[36m{spinner}\033[0m \033[2mGenerating...\033[0m"]

        # Add interrupt hint
        if self.show_interrupt_hint:
            parts.append("\033[2m(Ctrl+C to interrupt)\033[0m")

        # Add token counter if enabled and above threshold
        if self.show_tokens and self._token_count > self.TOKEN_DISPLAY_THRESHOLD:
            parts.append(f"\033[2m↓{self._token_count} tokens\033[0m")

        # Add "slow response" indicator if it's taking a while
        elapsed = time.time() - self._start_time
        if elapsed > self.SLOW_RESPONSE_THRESHOLD:
            parts.append(f"\033[2m({elapsed:.0f}s)\033[0m")

        message = " ".join(parts)

        # Only update if changed (reduces flicker)
        if message != self._last_output:
            self._clear_line()
            print(message, end="", flush=True)
            self._last_output = message

    def _clear_line(self):
        """Clear the current line."""
        # Move to start of line and clear to end
        print("\r\033[K", end="", flush=True)


def stream_completion(completion_call, show_progress: bool = True):
    """
    Wrapper to add streaming progress indicator to any LiteLLM completion call.

    This function attempts to use streaming mode for visual feedback. If streaming
    fails or is not supported, it falls back to blocking mode with a simple spinner.

    Args:
        completion_call: Callable that makes the litellm.completion() call
        show_progress: Whether to show progress indicator

    Returns:
        The completion response (same format as litellm.completion)

    Example:
        def make_call():
            return litellm.completion(
                model="gpt-4",
                messages=[{"role": "user", "content": "Hello"}],
                stream=True
            )

        response = stream_completion(make_call)
    """
    if not show_progress:
        # No progress indicator - just call directly
        return completion_call(stream=False)

    try:
        # Try streaming mode
        stream = completion_call(stream=True)

        renderer = StreamRenderer()
        renderer.start()

        # Accumulate response
        accumulated_content = ""
        accumulated_tool_calls = []
        response_model = None
        response_usage = None
        finish_reason = None

        token_count = 0

        try:
            for chunk in stream:
                # Track tokens (approximate - count chunks)
                token_count += 1
                renderer.update_tokens(token_count)

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # Accumulate content
                if hasattr(delta, "content") and delta.content:
                    accumulated_content += delta.content

                # Accumulate tool calls
                if hasattr(delta, "tool_calls") and delta.tool_calls:
                    for tc in delta.tool_calls:
                        # Ensure we have enough slots
                        while len(accumulated_tool_calls) <= tc.index:
                            accumulated_tool_calls.append(
                                {
                                    "id": None,
                                    "type": "function",
                                    "function": {"name": "", "arguments": ""},
                                }
                            )

                        # Update tool call data
                        if tc.id:
                            accumulated_tool_calls[tc.index]["id"] = tc.id
                        if hasattr(tc, "function"):
                            if tc.function.name:
                                accumulated_tool_calls[tc.index]["function"]["name"] = (
                                    tc.function.name
                                )
                            if tc.function.arguments:
                                accumulated_tool_calls[tc.index]["function"]["arguments"] += (
                                    tc.function.arguments
                                )

                # Store finish reason
                if hasattr(chunk.choices[0], "finish_reason") and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason

                # Store model info
                if hasattr(chunk, "model"):
                    response_model = chunk.model

                # Store usage info (usually comes in the last chunk)
                if hasattr(chunk, "usage") and chunk.usage:
                    response_usage = chunk.usage

        finally:
            renderer.stop()

        # Build complete response object (mimics litellm.completion format)
        # We need to return something that looks like ModelResponse
        from litellm.utils import Choices, Message, ModelResponse

        # Convert accumulated tool calls to proper format
        tool_calls_obj = None
        if accumulated_tool_calls:
            from litellm.types.utils import ChatCompletionMessageToolCall, Function

            tool_calls_obj = [
                ChatCompletionMessageToolCall(
                    id=tc["id"],
                    type="function",
                    function=Function(
                        name=tc["function"]["name"], arguments=tc["function"]["arguments"]
                    ),
                )
                for tc in accumulated_tool_calls
                if tc["id"]  # Only include complete tool calls
            ]

        # Create message object
        message = Message(
            content=accumulated_content or None, role="assistant", tool_calls=tool_calls_obj
        )

        # Create choice object
        choice = Choices(finish_reason=finish_reason or "stop", index=0, message=message)

        # Create response object
        response = ModelResponse(
            id="chatcmpl-streaming",
            choices=[choice],
            created=int(time.time()),
            model=response_model or "unknown",
            object="chat.completion",
            usage=response_usage,
        )

        return response

    except Exception:
        # Streaming failed - fall back to blocking mode with simple spinner
        renderer = StreamRenderer(show_tokens=False)
        renderer.start()

        try:
            response = completion_call(stream=False)
            return response
        finally:
            renderer.stop()
