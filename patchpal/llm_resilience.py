"""Network resilience utilities for LLM API calls.

Provides retry logic, connection management, and timeout handling to prevent
hangs when network connections are unstable or briefly interrupted.
"""

import random
import time
from typing import Any, Dict, List, Optional

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

import litellm


class NetworkResilientLLM:
    """Wrapper for LiteLLM calls with network resilience.

    Features:
    - Automatic retries with exponential backoff
    - Socket-level timeouts to detect stale connections
    - Connection health checks
    - Graceful degradation on network issues
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        timeout: int = 300,
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
    ):
        """Initialize the resilient LLM wrapper.

        Args:
            max_retries: Maximum number of retry attempts (default: 3)
            base_delay: Base delay in seconds for exponential backoff (default: 1.0)
            max_delay: Maximum delay between retries in seconds (default: 60.0)
            timeout: Overall request timeout in seconds (default: 300)
            connect_timeout: Connection establishment timeout in seconds (default: 10.0)
            read_timeout: Read timeout for detecting stale connections (default: 60.0)
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

        # Configure httpx client with aggressive timeouts
        # This is used by litellm under the hood
        self._configure_httpx()

    def _configure_httpx(self):
        """Configure httpx with socket-level timeouts.

        Sets up connection pooling and timeout configuration that LiteLLM
        will use for HTTP requests.
        """
        # Skip if httpx is not available (fallback to litellm defaults)
        if not HTTPX_AVAILABLE:
            return

        # Configure default httpx timeout for all litellm requests
        # This affects the underlying HTTP client behavior
        timeout_config = httpx.Timeout(
            timeout=self.timeout,
            connect=self.connect_timeout,
            read=self.read_timeout,
            write=30.0,  # Write timeout for request body
            pool=5.0,  # Timeout for acquiring connection from pool
        )

        # Store original client_session if it exists
        if not hasattr(litellm, "_original_client_session"):
            litellm._original_client_session = getattr(litellm, "client_session", None)

        # Create custom httpx client with our timeout settings
        # LiteLLM will use this for all requests
        litellm.client_session = httpx.Client(
            timeout=timeout_config,
            limits=httpx.Limits(
                max_connections=100,
                max_keepalive_connections=20,
                keepalive_expiry=30.0,  # Close idle connections after 30s
            ),
            transport=httpx.HTTPTransport(
                retries=0,  # We handle retries at a higher level
            ),
        )

    def _is_retryable_error(self, error: Exception) -> bool:
        """Determine if an error is retryable.

        Args:
            error: The exception that occurred

        Returns:
            True if the error is likely due to transient network issues
        """
        error_str = str(error).lower()

        # Network-related errors that should be retried
        retryable_patterns = [
            "timeout",
            "timed out",
            "connection reset",
            "connection refused",
            "connection error",
            "broken pipe",
            "read timeout",
            "connect timeout",
            "socket",
            "network",
            "temporary failure",
            "503",  # Service unavailable
            "502",  # Bad gateway
            "504",  # Gateway timeout
            "429",  # Rate limit (with backoff)
        ]

        return any(pattern in error_str for pattern in retryable_patterns)

    def completion(
        self,
        model: str,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: str = "auto",
        **kwargs,
    ) -> Any:
        """Call LiteLLM completion with automatic retries and resilience.

        Args:
            model: Model identifier
            messages: Conversation messages
            tools: Tool definitions
            tool_choice: Tool selection strategy
            **kwargs: Additional arguments for litellm.completion()

        Returns:
            LiteLLM completion response

        Raises:
            Exception: If all retries are exhausted
        """
        last_error = None
        attempt = 0

        while attempt <= self.max_retries:
            try:
                # Call LiteLLM with configured timeout
                response = litellm.completion(
                    model=model,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    timeout=self.timeout,
                    **kwargs,
                )
                return response

            except KeyboardInterrupt:
                # Don't retry on user interruption
                raise

            except Exception as e:
                last_error = e
                attempt += 1

                # Check if error is retryable
                if not self._is_retryable_error(e):
                    # Non-retryable error (e.g., authentication, invalid request)
                    raise

                # Don't retry if we've exhausted attempts
                if attempt > self.max_retries:
                    break

                # Calculate backoff delay with exponential increase
                delay = min(self.base_delay * (2 ** (attempt - 1)), self.max_delay)

                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, delay * 0.1)
                delay += jitter

                print(
                    f"\033[1;33m⚠️  Network error: {str(e)[:100]}\033[0m",
                    flush=True,
                )
                print(
                    f"\033[2m   Retrying in {delay:.1f}s (attempt {attempt}/{self.max_retries})...\033[0m",
                    flush=True,
                )

                time.sleep(delay)

                # Recreate httpx client to clear any stale connections
                self._configure_httpx()

        # All retries exhausted
        error_msg = f"LLM API call failed after {self.max_retries} retries: {last_error}"
        raise Exception(error_msg)

    def cleanup(self):
        """Clean up resources and restore original configuration."""
        # Close current client session
        if hasattr(litellm, "client_session") and litellm.client_session:
            try:
                litellm.client_session.close()
            except Exception:
                pass

        # Restore original client session if it existed
        if hasattr(litellm, "_original_client_session"):
            litellm.client_session = litellm._original_client_session
            delattr(litellm, "_original_client_session")


def create_resilient_llm(
    timeout: int = 300,
    max_retries: int = 3,
    connect_timeout: float = 10.0,
    read_timeout: float = 60.0,
) -> NetworkResilientLLM:
    """Create a network-resilient LLM wrapper.

    Args:
        timeout: Overall request timeout in seconds (default: 300)
        max_retries: Maximum number of retry attempts (default: 3)
        connect_timeout: Connection establishment timeout (default: 10.0)
        read_timeout: Read timeout for detecting stale connections (default: 60.0)

    Returns:
        Configured NetworkResilientLLM instance
    """
    return NetworkResilientLLM(
        max_retries=max_retries,
        timeout=timeout,
        connect_timeout=connect_timeout,
        read_timeout=read_timeout,
    )
