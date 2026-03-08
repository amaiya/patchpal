"""OAuth authentication for PatchPal."""

from .copilot import (
    COPILOT_HEADERS,
    CopilotCredentials,
    clear_copilot_credentials,
    get_base_url_from_token,
    get_copilot_auth_path,
    get_valid_copilot_token,
    is_copilot_logged_in,
    load_copilot_credentials,
)
from .copilot import login as copilot_login
from .openai import (
    OpenAICredentials,
    clear_openai_credentials,
    get_openai_auth_path,
    get_valid_openai_token,
    is_openai_logged_in,
    load_openai_credentials,
)
from .openai import login as openai_login

__all__ = [
    "COPILOT_HEADERS",
    "CopilotCredentials",
    "OpenAICredentials",
    "clear_copilot_credentials",
    "clear_openai_credentials",
    "copilot_login",
    "get_base_url_from_token",
    "get_copilot_auth_path",
    "get_openai_auth_path",
    "get_valid_copilot_token",
    "get_valid_openai_token",
    "is_copilot_logged_in",
    "is_openai_logged_in",
    "load_copilot_credentials",
    "load_openai_credentials",
    "openai_login",
]
