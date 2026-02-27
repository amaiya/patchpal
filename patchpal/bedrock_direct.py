"""Direct boto3 backend for AWS Bedrock (bypassing LiteLLM).

This module provides a direct boto3 interface to AWS Bedrock, similar to the
onprem library's approach. It's used when PATCHPAL_BEDROCK_DIRECT=true to
bypass LiteLLM's abstraction layer, which can cause intermittent issues in
certain network environments (e.g., IDA GovCloud with network security appliances).
"""

import json
import os
from typing import Any, Dict, List, Optional


class DirectBedrockClient:
    """Direct boto3 client for AWS Bedrock (bypassing LiteLLM).

    This implementation mirrors the approach used in the onprem library's
    ChatGovCloudBedrock class. It provides a simpler, more reliable connection
    path by using boto3 directly without LiteLLM's abstraction layer.
    """

    def __init__(
        self,
        model_id: str,
        region_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ):
        """Initialize direct Bedrock client.

        Args:
            model_id: Bedrock model ID (with or without bedrock/ prefix)
            region_name: AWS region (defaults to AWS_BEDROCK_REGION or AWS_REGION env var)
            endpoint_url: Custom endpoint URL (defaults to AWS_BEDROCK_ENDPOINT env var)
            max_tokens: Maximum tokens to generate (optional, uses Bedrock's model default if None)
            temperature: Sampling temperature (optional, uses Bedrock's model default if None)
        """
        # Strip bedrock/ prefix if present
        if model_id.startswith("bedrock/"):
            model_id = model_id[len("bedrock/") :]

        self.model_id = model_id
        self.max_tokens = max_tokens  # Can be None to use model defaults
        self.temperature = temperature  # Can be None to use model defaults

        # Determine region from environment or parameter
        self.region_name = (
            region_name
            or os.getenv("AWS_BEDROCK_REGION")
            or os.getenv("AWS_REGION")
            or os.getenv("AWS_DEFAULT_REGION")
            or os.getenv("AWS_REGION_NAME")
            or "us-east-1"
        )

        # Determine endpoint from environment or parameter
        self.endpoint_url = (
            endpoint_url
            or os.getenv("AWS_BEDROCK_ENDPOINT")
            or os.getenv("AWS_BEDROCK_RUNTIME_ENDPOINT")
        )

        # Initialize boto3 client
        self._init_client()

    def _init_client(self):
        """Initialize boto3 bedrock-runtime client."""
        try:
            import boto3
        except ImportError:
            raise ImportError(
                "boto3 is required for direct Bedrock access. Install with: pip install boto3"
            )

        client_kwargs = {
            "service_name": "bedrock-runtime",
            "region_name": self.region_name,
        }

        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url

        # Use credentials from environment
        # boto3 will automatically use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY

        self.client = boto3.client(**client_kwargs)

        print("\033[2m   Direct Bedrock client initialized:")
        print(f"   Region: {self.region_name}")
        if self.endpoint_url:
            print(f"   Endpoint: {self.endpoint_url}")
        print("\033[0m", flush=True)

    def _convert_messages_to_bedrock_format(
        self, messages: List[Dict[str, Any]]
    ) -> tuple[Optional[str], List[Dict[str, Any]]]:
        """Convert OpenAI-style messages to Bedrock format.

        Args:
            messages: List of OpenAI-style message dicts with 'role' and 'content'

        Returns:
            Tuple of (system_prompt, bedrock_messages)
        """
        system_prompt = None
        system_prompt_blocks = []  # For structured system with cache markers
        bedrock_messages = []

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")

            if role == "system":
                # Handle system messages - preserve cache markers if present
                if isinstance(content, list):
                    # Structured content with potential cache markers - preserve it
                    system_prompt_blocks.extend(content)
                elif isinstance(content, str):
                    # Simple string content
                    if system_prompt is None:
                        system_prompt = content
                    else:
                        system_prompt += f"\n\n{content}"
                else:
                    # Fallback to string
                    content_str = str(content)
                    if system_prompt is None:
                        system_prompt = content_str
                    else:
                        system_prompt += f"\n\n{content_str}"

            elif role == "user" or role == "assistant":
                # Handle user/assistant messages - preserve structure if present
                if isinstance(content, list):
                    # Structured content (with potential cache markers) - pass through as-is
                    bedrock_messages.append({"role": role, "content": content})
                elif isinstance(content, str):
                    # Simple string content
                    bedrock_messages.append({"role": role, "content": content})
                else:
                    # Fallback to string
                    bedrock_messages.append({"role": role, "content": str(content)})

            elif role == "tool":
                # Tool results are appended as user messages
                tool_name = msg.get("name", "tool")
                # Extract text from content
                if isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            text_parts.append(str(block.get("text", "")))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)
                elif not isinstance(content, str):
                    content = str(content)

                bedrock_messages.append(
                    {"role": "user", "content": f"Tool result from {tool_name}:\n{content}"}
                )

        # Return system prompt - prefer structured format if we have blocks with cache markers
        if system_prompt_blocks:
            return system_prompt_blocks, bedrock_messages
        else:
            return system_prompt, bedrock_messages

    def _convert_tools_to_bedrock_format(
        self, tools: Optional[List[Dict[str, Any]]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert OpenAI-style tools to Bedrock format.

        Args:
            tools: List of OpenAI-style tool definitions

        Returns:
            List of Bedrock-style tool definitions, or None
        """
        if not tools:
            return None

        bedrock_tools = []
        for tool in tools:
            if tool.get("type") == "function":
                func = tool.get("function", {})
                bedrock_tool = {
                    "name": func.get("name", ""),
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {}),
                }
                bedrock_tools.append(bedrock_tool)

        return bedrock_tools if bedrock_tools else None

    def completion(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs: Any,
    ) -> Any:
        """Call Bedrock API directly (bypassing LiteLLM).

        Args:
            messages: OpenAI-style messages
            tools: OpenAI-style tool definitions
            tool_choice: Tool choice strategy ("auto", "none", etc.)
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            OpenAI-compatible response object
        """
        # Convert messages to Bedrock format
        system_prompt, bedrock_messages = self._convert_messages_to_bedrock_format(messages)

        # Build request body (start with required fields)
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": bedrock_messages,
        }

        # Add max_tokens if specified (either from kwargs, instance default, or use Bedrock's default)
        max_tokens = kwargs.get("max_tokens", self.max_tokens)
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        else:
            # Bedrock requires max_tokens for Claude models - use a reasonable default
            body["max_tokens"] = 4096

        # Add temperature if specified (optional - Bedrock will use model default if not provided)
        temperature = kwargs.get("temperature", self.temperature)
        if temperature is not None:
            body["temperature"] = temperature

        # Add system prompt if present
        if system_prompt:
            # system_prompt can be either a string or a list of content blocks (with cache markers)
            if isinstance(system_prompt, list):
                # Structured format with cache markers - pass through as-is
                body["system"] = system_prompt
            elif isinstance(system_prompt, str):
                # Simple string format
                body["system"] = system_prompt
            else:
                # Fallback: convert to string
                body["system"] = str(system_prompt)

        # Add tools if present
        bedrock_tools = self._convert_tools_to_bedrock_format(tools)
        if bedrock_tools:
            body["tools"] = bedrock_tools

            # Convert tool_choice (only set if not "auto", to use Bedrock's default)
            # Note: Bedrock defaults to "auto" when tool_choice is omitted
            if tool_choice and tool_choice != "auto":
                if tool_choice == "none":
                    # Don't set tool_choice - omitting it when tools are present means auto
                    pass
                elif isinstance(tool_choice, dict):
                    # Specific tool choice
                    body["tool_choice"] = tool_choice
                else:
                    # Unknown value - pass through
                    body["tool_choice"] = tool_choice

        try:
            # Make the API call using boto3 directly
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body).encode("utf-8"),
            )

            # Parse response
            response_body = json.loads(response["body"].read().decode("utf-8"))

            # Convert Bedrock response to OpenAI format
            return self._convert_response_to_openai_format(response_body)

        except Exception as e:
            raise RuntimeError(f"Direct Bedrock API call failed: {str(e)}")

    def _convert_response_to_openai_format(self, bedrock_response: Dict[str, Any]) -> Any:
        """Convert Bedrock response to OpenAI format.

        Args:
            bedrock_response: Raw Bedrock API response

        Returns:
            OpenAI-compatible response object
        """
        from types import SimpleNamespace

        # Map Bedrock stop_reason to OpenAI finish_reason
        stop_reason = bedrock_response.get("stop_reason", "stop")
        finish_reason_map = {
            "end_turn": "stop",
            "stop_sequence": "stop",
            "max_tokens": "length",
            "tool_use": "tool_calls",
            "content_filtered": "content_filter",
        }
        finish_reason = finish_reason_map.get(stop_reason, stop_reason)

        # Extract content
        content_blocks = bedrock_response.get("content", [])

        # Build response text and tool calls
        message_content = ""
        tool_calls = []

        for block in content_blocks:
            if block.get("type") == "text":
                message_content = block.get("text", "")
            elif block.get("type") == "tool_use":
                # Convert to OpenAI tool call format
                tool_call = SimpleNamespace(
                    id=block.get("id", ""),
                    type="function",
                    function=SimpleNamespace(
                        name=block.get("name", ""), arguments=json.dumps(block.get("input", {}))
                    ),
                )
                tool_calls.append(tool_call)

        # Build OpenAI-compatible message
        message = SimpleNamespace(
            role="assistant",
            content=message_content if message_content else None,
            tool_calls=tool_calls if tool_calls else None,
        )

        # Build choice
        choice = SimpleNamespace(
            index=0,
            message=message,
            finish_reason=finish_reason,  # Use mapped finish_reason, not raw stop_reason
        )

        # Build usage
        usage_data = bedrock_response.get("usage", {})

        # Bedrock returns usage as:
        # - input_tokens: non-cached input tokens only
        # - cache_creation_input_tokens: tokens written to cache (125% cost)
        # - cache_read_input_tokens: tokens read from cache (10% cost)
        # We need to sum all input token types for prompt_tokens to match LiteLLM format

        input_tokens = usage_data.get("input_tokens", 0)
        cache_creation_tokens = usage_data.get("cache_creation_input_tokens", 0)
        cache_read_tokens = usage_data.get("cache_read_input_tokens", 0)

        # Total prompt tokens = all input types combined
        total_prompt_tokens = input_tokens + cache_creation_tokens + cache_read_tokens

        usage = SimpleNamespace(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=usage_data.get("output_tokens", 0),
            total_tokens=total_prompt_tokens + usage_data.get("output_tokens", 0),
            # Add Bedrock cache statistics if present (for prompt caching)
            # Use None if not present, otherwise use actual value (including 0)
            cache_creation_input_tokens=cache_creation_tokens
            if cache_creation_tokens > 0
            else None,
            cache_read_input_tokens=cache_read_tokens if cache_read_tokens > 0 else None,
        )

        # Build full response
        response = SimpleNamespace(
            id=bedrock_response.get("id", ""),
            object="chat.completion",
            created=0,  # Bedrock doesn't provide timestamp
            model=self.model_id,
            choices=[choice],
            usage=usage,
        )

        return response


def create_direct_bedrock_client(model_id: str, **kwargs) -> DirectBedrockClient:
    """Create a direct Bedrock client (bypassing LiteLLM).

    Args:
        model_id: Bedrock model ID
        **kwargs: Additional parameters for DirectBedrockClient

    Returns:
        DirectBedrockClient instance
    """
    return DirectBedrockClient(model_id=model_id, **kwargs)
