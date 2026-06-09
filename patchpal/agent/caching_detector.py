"""Utility to detect prompt caching support for models without explicit model names."""

import litellm


def test_prompt_caching_support(model_id: str, litellm_kwargs: dict = None) -> bool:
    """Test if a model supports prompt caching by making a minimal test request.

    This is useful for application inference profiles (tagged profiles) where the
    underlying model name is not in the ARN, making it impossible to statically
    determine caching support.

    Args:
        model_id: Full LiteLLM model identifier (e.g., bedrock/converse/arn:...)
        litellm_kwargs: Optional kwargs to pass to litellm.completion

    Returns:
        True if prompt caching is supported, False otherwise
    """
    if litellm_kwargs is None:
        litellm_kwargs = {}

    # Create a minimal test message with cache markers
    test_messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What is the capital of France?",
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        }
    ]

    # Include a minimal tool to match real usage (some models only support caching without tools)
    test_tools = [
        {
            "type": "function",
            "function": {
                "name": "get_info",
                "description": "Get information",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "The query"}},
                    "required": ["query"],
                },
            },
        }
    ]

    try:
        # Try with Anthropic-style cache_control AND tools (matches real usage)
        litellm.completion(
            model=model_id,
            messages=test_messages,
            tools=test_tools,
            tool_choice="auto",  # Include tool_choice like the real agent
            max_tokens=10,
            **litellm_kwargs,
        )
        # If we got here without error, caching is supported
        return True
    except Exception as e:
        error_msg = str(e).lower()
        # Check for caching-specific errors
        if any(
            phrase in error_msg
            for phrase in [
                "prompt caching",
                "cache_control",
                "cachepoint",
                "unsupported model",
                "did not allow prompt caching",
            ]
        ):
            # Caching not supported
            return False
        else:
            # Different error (auth, network, etc.) - conservatively assume caching not supported
            return False
