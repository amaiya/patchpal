"""Tests for LLM network resilience."""

from unittest.mock import Mock, patch

import pytest

from patchpal.llm_resilience import NetworkResilientLLM


def test_resilient_llm_successful_call():
    """Test that successful LLM calls work normally."""
    resilient_llm = NetworkResilientLLM(max_retries=2)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Test response"))]

    with patch("litellm.completion") as mock_completion:
        mock_completion.return_value = mock_response

        response = resilient_llm.completion(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "test"}],
        )

        assert response == mock_response
        assert mock_completion.call_count == 1


def test_resilient_llm_retry_on_network_error():
    """Test that network errors trigger retries."""
    resilient_llm = NetworkResilientLLM(max_retries=2, base_delay=0.1)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Success after retry"))]

    with patch("litellm.completion") as mock_completion:
        # First call fails, second succeeds
        mock_completion.side_effect = [
            Exception("Connection timeout"),
            mock_response,
        ]

        response = resilient_llm.completion(
            model="anthropic/claude-3-5-sonnet-20241022",
            messages=[{"role": "user", "content": "test"}],
        )

        assert response == mock_response
        assert mock_completion.call_count == 2


def test_resilient_llm_exhausts_retries():
    """Test that retries are exhausted after max attempts."""
    resilient_llm = NetworkResilientLLM(max_retries=2, base_delay=0.1)

    with patch("litellm.completion") as mock_completion:
        # All calls fail
        mock_completion.side_effect = Exception("Network error")

        with pytest.raises(Exception, match="failed after 2 retries"):
            resilient_llm.completion(
                model="anthropic/claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": "test"}],
            )

        assert mock_completion.call_count == 3  # Initial + 2 retries


def test_resilient_llm_non_retryable_error():
    """Test that non-retryable errors fail immediately."""
    resilient_llm = NetworkResilientLLM(max_retries=2)

    with patch("litellm.completion") as mock_completion:
        # Non-retryable error (authentication)
        mock_completion.side_effect = Exception("Invalid API key")

        with pytest.raises(Exception, match="Invalid API key"):
            resilient_llm.completion(
                model="anthropic/claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": "test"}],
            )

        # Should not retry
        assert mock_completion.call_count == 1


def test_resilient_llm_keyboard_interrupt():
    """Test that KeyboardInterrupt is not retried."""
    resilient_llm = NetworkResilientLLM(max_retries=2)

    with patch("litellm.completion") as mock_completion:
        mock_completion.side_effect = KeyboardInterrupt()

        with pytest.raises(KeyboardInterrupt):
            resilient_llm.completion(
                model="anthropic/claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": "test"}],
            )

        # Should not retry on user interruption
        assert mock_completion.call_count == 1


def test_resilient_llm_exponential_backoff():
    """Test that retry delays follow exponential backoff."""
    resilient_llm = NetworkResilientLLM(max_retries=3, base_delay=0.1, max_delay=1.0)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Success"))]

    with patch("litellm.completion") as mock_completion:
        with patch("time.sleep") as mock_sleep:
            # Fail 3 times, succeed on 4th
            mock_completion.side_effect = [
                Exception("timeout"),
                Exception("timeout"),
                Exception("timeout"),
                mock_response,
            ]

            resilient_llm.completion(
                model="anthropic/claude-3-5-sonnet-20241022",
                messages=[{"role": "user", "content": "test"}],
            )

            # Check sleep was called with increasing delays
            assert mock_sleep.call_count == 3
            delays = [call[0][0] for call in mock_sleep.call_args_list]
            # Delays should be roughly 0.1, 0.2, 0.4 (with jitter)
            assert delays[0] < delays[1] < delays[2]


def test_is_retryable_error():
    """Test error classification."""
    resilient_llm = NetworkResilientLLM()

    # Retryable errors
    assert resilient_llm._is_retryable_error(Exception("Connection timeout"))
    assert resilient_llm._is_retryable_error(Exception("Read timeout"))
    assert resilient_llm._is_retryable_error(Exception("503 Service Unavailable"))
    assert resilient_llm._is_retryable_error(Exception("Network error"))

    # Non-retryable errors
    assert not resilient_llm._is_retryable_error(Exception("Invalid API key"))
    assert not resilient_llm._is_retryable_error(Exception("Authentication failed"))
    assert not resilient_llm._is_retryable_error(Exception("400 Bad Request"))
