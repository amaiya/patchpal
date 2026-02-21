"""Image handling utilities for vision model support.

Handles provider-specific image formatting (OpenAI vs Anthropic),
pending image management, and image blocking for non-vision models.
"""

from typing import Any, Dict, List, Optional, Tuple

from patchpal.config import config


class ImageHandler:
    """Handles image processing for vision-capable LLMs.

    Different providers handle images differently:
    - Anthropic/Claude: Supports images directly in tool results (multimodal content)
    - OpenAI: Doesn't support images in tool results, requires injection as user message

    This class abstracts these differences and provides a unified interface.
    """

    def __init__(self, model_id: str):
        """Initialize image handler.

        Args:
            model_id: LiteLLM model identifier (used to detect provider)
        """
        self.model_id = model_id
        self._pending_images: List[Dict[str, str]] = []

        # Safety limits for pending images (OpenAI workaround)
        self.max_pending_images = 20
        self.max_pending_size_mb = 50  # Conservative limit (~67MB base64)

    def is_openai_model(self) -> bool:
        """Check if model is OpenAI-based (needs special image handling).

        Returns:
            True if model uses OpenAI API
        """
        model_lower = self.model_id.lower()
        return (
            "openai" in model_lower or "gpt" in model_lower or self.model_id.startswith("openai/")
        )

    def parse_image_data(self, result_str: str) -> Optional[Tuple[str, str]]:
        """Parse IMAGE_DATA format string from tool results.

        Args:
            result_str: Result string that may contain IMAGE_DATA format

        Returns:
            Tuple of (mime_type, base64_data) if valid IMAGE_DATA, None otherwise
        """
        if not result_str.startswith("IMAGE_DATA:"):
            return None

        # Parse: IMAGE_DATA:mime:base64data
        parts = result_str.split(":", 2)
        if len(parts) == 3:
            _, mime, b64_data = parts
            # Validate that both mime and base64 are non-empty
            if mime and b64_data:
                return (mime, b64_data)

        return None

    def add_image_tool_result(
        self,
        messages: List[Dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        mime: str,
        b64_data: str,
    ) -> None:
        """Add image tool result with provider-specific formatting.

        Args:
            messages: Message list to append to
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            mime: MIME type of the image
            b64_data: Base64-encoded image data
        """
        if self.is_openai_model():
            self._add_image_tool_result_openai(messages, tool_call_id, tool_name, mime, b64_data)
        else:
            self._add_image_tool_result_anthropic(messages, tool_call_id, tool_name, mime, b64_data)

    def _add_image_tool_result_openai(
        self,
        messages: List[Dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        mime: str,
        b64_data: str,
    ) -> None:
        """Handle image tool result for OpenAI (store pending, add text-only result).

        OpenAI doesn't support images in tool results, so we store the image
        and inject it as a user message after the assistant responds.

        Args:
            messages: Message list to append to
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            mime: MIME type of the image
            b64_data: Base64-encoded image data
        """
        # Add text-only tool result
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": "Image loaded successfully (see attached image below)",
            }
        )

        # Check safety limits before adding
        pending_count = len(self._pending_images)
        pending_size_mb = sum(len(img["data"]) for img in self._pending_images) / (1024 * 1024)
        current_size_mb = len(b64_data) / (1024 * 1024)

        if pending_count >= self.max_pending_images:
            print(
                f"\033[1;33m⚠️  Warning: Already have {pending_count} pending images. "
                f"Skipping additional image to prevent memory issues.\033[0m"
            )
            # Update tool result with warning
            messages[-1]["content"] = (
                f"Image loaded but not attached (already have {pending_count} pending images in this turn). "
                f"Consider processing images in smaller batches."
            )
            return

        if pending_size_mb + current_size_mb > self.max_pending_size_mb:
            print(
                f"\033[1;33m⚠️  Warning: Pending images total {pending_size_mb:.1f}MB. "
                f"Adding {current_size_mb:.1f}MB would exceed {self.max_pending_size_mb}MB limit.\033[0m"
            )
            # Update tool result with warning
            messages[-1]["content"] = (
                f"Image loaded but not attached (would exceed {self.max_pending_size_mb}MB memory limit). "
                f"Current pending: {pending_size_mb:.1f}MB, this image: {current_size_mb:.1f}MB."
            )
            return

        # Store pending image to inject later
        self._pending_images.append(
            {
                "mime": mime,
                "data": b64_data,
            }
        )

        print(
            f"\033[2m   → Image loaded ({len(b64_data):,} chars base64, will inject as user message for OpenAI)\033[0m"
        )

    def _add_image_tool_result_anthropic(
        self,
        messages: List[Dict[str, Any]],
        tool_call_id: str,
        tool_name: str,
        mime: str,
        b64_data: str,
    ) -> None:
        """Handle image tool result for Anthropic/Claude (multimodal content).

        Anthropic supports images directly in tool results as multimodal content.

        Args:
            messages: Message list to append to
            tool_call_id: ID of the tool call
            tool_name: Name of the tool
            mime: MIME type of the image
            b64_data: Base64-encoded image data
        """
        messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "content": [
                    {"type": "text", "text": "Image loaded successfully"},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{b64_data}"},
                    },
                ],
            }
        )
        print(
            f"\033[2m   → Image loaded ({len(b64_data):,} chars base64, formatted as multimodal content)\033[0m"
        )

    def inject_pending_images(self, messages: List[Dict[str, Any]]) -> None:
        """Inject pending images as user message for OpenAI.

        OpenAI doesn't support images in tool results, so we collect them
        and inject as a separate user message after the assistant responds.

        Args:
            messages: Message list to append to
        """
        if not self._pending_images:
            return

        image_content = [
            {
                "type": "text",
                "text": "Here are the image(s) from the tool result:",
            }
        ]

        for img in self._pending_images:
            image_content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{img['mime']};base64,{img['data']}"},
                }
            )

        messages.append(
            {
                "role": "user",
                "content": image_content,
            }
        )

        print(
            f"\033[2m   → Injected {len(self._pending_images)} image(s) as user message for OpenAI\033[0m"
        )

        # Clear pending images after injection
        self._pending_images = []

    def clear_pending_images(self) -> None:
        """Clear any pending images (for error cleanup)."""
        self._pending_images = []

    def has_pending_images(self) -> bool:
        """Check if there are pending images waiting to be injected.

        Returns:
            True if there are pending images
        """
        return len(self._pending_images) > 0

    @staticmethod
    def filter_images_if_blocked(messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Filter images from messages if PATCHPAL_BLOCK_IMAGES is enabled.

        Replaces image content with text placeholders to support non-vision models
        or when user explicitly wants to block images (cost/privacy).

        Args:
            messages: List of message dictionaries

        Returns:
            Filtered messages with images replaced by text if blocking is enabled
        """
        if not config.BLOCK_IMAGES:
            return messages

        filtered = []
        for msg in messages:
            # Only filter user and tool messages that might contain images
            if msg.get("role") in ["user", "tool"] and isinstance(msg.get("content"), list):
                filtered_content = []
                for block in msg["content"]:
                    if isinstance(block, dict) and block.get("type") == "image_url":
                        # Replace image with text placeholder
                        filtered_content.append(
                            {
                                "type": "text",
                                "text": "[Image blocked - PATCHPAL_BLOCK_IMAGES=true. Set to false to enable vision capabilities.]",
                            }
                        )
                    else:
                        filtered_content.append(block)

                # Dedupe consecutive image block placeholders
                deduped = []
                last_was_blocked = False
                for block in filtered_content:
                    is_blocked = (
                        isinstance(block, dict)
                        and block.get("type") == "text"
                        and block.get("text", "").startswith("[Image blocked")
                    )
                    if not (is_blocked and last_was_blocked):
                        deduped.append(block)
                    last_was_blocked = is_blocked

                filtered.append({**msg, "content": deduped})
            else:
                filtered.append(msg)

        return filtered

    @staticmethod
    def should_skip_pruning(content: Any) -> bool:
        """Check if message content should skip pruning (contains images).

        Args:
            content: Message content (string or list)

        Returns:
            True if content contains images and should not be pruned
        """
        if not isinstance(content, list):
            return False

        # Check if list contains any image blocks
        has_images = any(
            isinstance(block, dict) and block.get("type") == "image_url" for block in content
        )
        return has_images
