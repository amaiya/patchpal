"""Utilities for AWS Bedrock application inference profiles.

Application inference profiles (tagged profiles) don't include model names in their ARNs,
making it impossible to statically determine model capabilities or pricing. This module
provides functions to detect the underlying model and its capabilities at runtime.
"""

import litellm


def _extract_model_from_arn(arn: str) -> str | None:
    """Try to extract underlying model info from an inference profile ARN using AWS API.

    Args:
        arn: The inference profile ARN

    Returns:
        Model name if found, None otherwise
    """
    try:
        import os

        import boto3

        # Extract region from ARN (arn:aws-us-gov:bedrock:us-gov-east-1:...)
        parts = arn.split(":")
        if len(parts) >= 4:
            region = parts[3]
        else:
            region = os.getenv("AWS_REGION_NAME") or os.getenv("AWS_REGION") or "us-east-1"

        # Check for custom Bedrock RUNTIME endpoint (for reference/debugging only)
        # Note: We don't use runtime endpoint for control plane API
        runtime_endpoint = (
            os.getenv("AWS_BEDROCK_ENDPOINT")  # PatchPal-specific (runtime only)
            or os.getenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME")  # AWS SDK standard (runtime)
        )

        # Determine control plane endpoint for get_inference_profile API
        # Priority order:
        # 1. Explicit control plane endpoint variables
        # 2. None (let boto3 use default public endpoint)
        control_endpoint = (
            os.getenv("AWS_ENDPOINT_URL_BEDROCK")  # AWS SDK standard (control plane)
            or os.getenv("AWS_BEDROCK_CONTROL_ENDPOINT")  # PatchPal-specific (control plane)
        )

        # If no explicit control plane endpoint, let boto3 use default endpoint resolution
        # This handles:
        # - Standard AWS regions (bedrock.us-east-1.amazonaws.com)
        # - GovCloud regions (bedrock.us-gov-east-1.amazonaws.com)
        # - FIPS endpoints (if configured in boto3)
        #
        # IMPORTANT: Even if user has AWS_BEDROCK_ENDPOINT (runtime VPC endpoint),
        # we DON'T use it for control plane because:
        # 1. AWS_BEDROCK_ENDPOINT is runtime-only (for inference)
        # 2. Many users only create runtime VPC endpoint
        # 3. Control plane API is read-only and less sensitive
        # 4. Public control plane endpoint is often acceptable
        # 5. If user needs control plane VPC endpoint, they should set:
        #    AWS_ENDPOINT_URL_BEDROCK or AWS_BEDROCK_CONTROL_ENDPOINT

        # Debug output
        if os.getenv("PATCHPAL_DEBUG") == "true":
            import sys

            print("\n\033[2m[DEBUG] Control plane endpoint determination:\033[0m", file=sys.stderr)
            print(
                f"\033[2m[DEBUG]   Runtime endpoint (not used): {runtime_endpoint or 'None'}\033[0m",
                file=sys.stderr,
            )
            print(
                f"\033[2m[DEBUG]   Control endpoint: {control_endpoint or 'boto3 default (public)'}\033[0m",
                file=sys.stderr,
            )

        # Create bedrock client
        if control_endpoint:
            bedrock = boto3.client("bedrock", region_name=region, endpoint_url=control_endpoint)
        else:
            # Let boto3 use default endpoint resolution (public endpoint)
            bedrock = boto3.client("bedrock", region_name=region)

        # Get inference profile details
        response = bedrock.get_inference_profile(inferenceProfileIdentifier=arn)

        # Extract model info from response
        if "models" in response and response["models"]:
            # Get first model from the profile
            first_model = response["models"][0]
            if "modelArn" in first_model:
                # Extract model ID from ARN
                # e.g., arn:aws-us-gov:bedrock:us-gov-west-1::foundation-model/anthropic.claude-sonnet-4-5-20250929-v1:0
                model_arn = first_model["modelArn"]

                # Try multiple extraction methods
                if "foundation-model" in model_arn:
                    # Split on the foundation-model part
                    parts = model_arn.split("foundation-model/")
                    if len(parts) > 1:
                        return parts[1]

        return None
    except ImportError as e:
        # boto3 not available - can't query AWS API
        import os

        if os.getenv("PATCHPAL_DEBUG") == "true":
            import sys

            print(
                f"\n\033[2m[DEBUG] boto3 not available, cannot extract model from ARN: {e}\033[0m",
                file=sys.stderr,
            )
        return None
    except Exception as e:
        # API call failed
        # Add debug logging for troubleshooting
        import os

        if os.getenv("PATCHPAL_DEBUG") == "true":
            import sys

            print(f"\n\033[2m[DEBUG] Failed to extract model from ARN: {e}\033[0m", file=sys.stderr)
            print(f"\033[2m[DEBUG] ARN: {arn}\033[0m", file=sys.stderr)
            print(
                f"\033[2m[DEBUG] Region: {region if 'region' in locals() else 'unknown'}\033[0m",
                file=sys.stderr,
            )
            print(
                f"\033[2m[DEBUG] Control endpoint: {control_endpoint if 'control_endpoint' in locals() else 'unknown'}\033[0m",
                file=sys.stderr,
            )
        return None


def detect_model_capabilities(
    model_id: str, litellm_kwargs: dict = None
) -> tuple[bool, str | None]:
    """Detect prompt caching support and underlying model name for application inference profiles.

    This is useful for application inference profiles (tagged profiles) where the
    underlying model name is not in the ARN, making it impossible to statically
    determine model capabilities or pricing.

    Args:
        model_id: Full LiteLLM model identifier (e.g., bedrock/converse/arn:...)
        litellm_kwargs: Optional kwargs to pass to litellm.completion

    Returns:
        Tuple of (caching_supported: bool, model_name: str | None)
        - caching_supported: True if prompt caching works with tools
        - model_name: Detected model name from response metadata (e.g., "claude-3-5-sonnet-20241022")
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

    caching_supported = False
    detected_model = None

    # For ARNs, try to get model info from AWS API first
    if "arn:aws" in model_id and "inference-profile" in model_id:
        # Extract just the ARN (remove bedrock/converse/ prefix if present)
        arn = model_id.replace("bedrock/converse/", "").replace("bedrock/", "")
        detected_model = _extract_model_from_arn(arn)

        # Debug output
        import os

        if os.getenv("PATCHPAL_DEBUG") == "true":
            import sys

            print(
                "\n\033[2m[DEBUG] Attempting to extract model from ARN via AWS API\033[0m",
                file=sys.stderr,
            )
            print(f"\033[2m[DEBUG] Full model_id: {model_id}\033[0m", file=sys.stderr)
            print(f"\033[2m[DEBUG] Extracted ARN: {arn}\033[0m", file=sys.stderr)
            print(f"\033[2m[DEBUG] Result from AWS API: {detected_model}\033[0m", file=sys.stderr)

    try:
        # Try with Anthropic-style cache_control AND tools (matches real usage)
        response = litellm.completion(
            model=model_id,
            messages=test_messages,
            tools=test_tools,
            tool_choice="auto",  # Include tool_choice like the real agent
            max_tokens=10,
            **litellm_kwargs,
        )
        # If we got here without error, caching is supported
        caching_supported = True

        # Only try to extract model from response if we didn't get it from AWS API
        if not detected_model:
            # Try to extract model name from response metadata
            # Bedrock responses include model info in various places
            if hasattr(response, "_hidden_params") and response._hidden_params:
                # LiteLLM stores raw response data here
                hidden = response._hidden_params

                # Check optional_params which may contain raw boto3 response
                if "optional_params" in hidden and isinstance(hidden["optional_params"], dict):
                    optional = hidden["optional_params"]
                    # Bedrock converse API may include model info in the response
                    if "model" in optional:
                        detected_model = optional["model"]
                    elif "modelId" in optional:
                        detected_model = optional["modelId"]

                # Check standard fields
                if not detected_model and "model_id" in hidden and hidden["model_id"]:
                    detected_model = hidden["model_id"]
                elif not detected_model and "model" in hidden and hidden["model"]:
                    detected_model = hidden["model"]

            # Check response metadata
            if not detected_model and hasattr(response, "model"):
                model_val = response.model
                # Skip if it's just the ARN we passed in
                if model_val and "application-inference-profile" not in model_val:
                    detected_model = model_val

            # Try to extract from response choices/usage if available
            if not detected_model and hasattr(response, "usage"):
                usage = response.usage
                if hasattr(usage, "model") and usage.model:
                    detected_model = usage.model

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
            # Caching not supported, but still try to detect model without caching
            caching_supported = False

            # Only retry if we don't already have model from AWS API
            if not detected_model:
                try:
                    # Retry without cache markers to detect model
                    simple_messages = [{"role": "user", "content": "Hi"}]
                    response = litellm.completion(
                        model=model_id,
                        messages=simple_messages,
                        tools=test_tools,
                        max_tokens=5,
                        **litellm_kwargs,
                    )
                    # Try to extract model from response
                    if hasattr(response, "_hidden_params") and response._hidden_params:
                        hidden = response._hidden_params
                        if "model_id" in hidden:
                            detected_model = hidden["model_id"]
                        elif "model" in hidden:
                            detected_model = hidden["model"]
                    if not detected_model and hasattr(response, "model"):
                        detected_model = response.model
                except Exception:
                    pass  # Could not detect model
        else:
            # Different error (auth, network, etc.)
            caching_supported = False

    return caching_supported, detected_model


def test_prompt_caching_support(model_id: str, litellm_kwargs: dict = None) -> bool:
    """Test if a model supports prompt caching (backward compatibility wrapper).

    Args:
        model_id: Full LiteLLM model identifier (e.g., bedrock/converse/arn:...)
        litellm_kwargs: Optional kwargs to pass to litellm.completion

    Returns:
        True if prompt caching is supported, False otherwise
    """
    caching_supported, _ = detect_model_capabilities(model_id, litellm_kwargs)
    return caching_supported
