"""Browser automation tools using Playwright.

Provides interactive browser capabilities for tasks requiring JavaScript execution,
form interaction, or visual rendering that web_fetch cannot handle.

Optional dependency: Install with `pip install patchpal[browser]` and run
`python -m playwright install chromium` to use these tools.
"""

import re
from pathlib import Path
from typing import Optional

from patchpal.config import config

try:
    from playwright.sync_api import Page, sync_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Page = None

from patchpal.tools.common import _get_permission_manager, _operation_limiter


class _BrowserState:
    """Singleton browser instance for persistent session across tool calls.

    Similar to OpenWorker's approach - one browser window that stays open
    across multiple operations, allowing for interactive workflows like:
    1. Navigate to login page
    2. Fill credentials
    3. Click submit
    4. Navigate to data page
    5. Extract content
    """

    _playwright = None
    _browser = None
    _context = None
    _page: Optional[Page] = None

    @classmethod
    def get_page(cls) -> Page:
        """Get or create browser page.

        Returns:
            Playwright Page object

        Raises:
            ValueError: If Playwright not installed
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ValueError(
                "Browser automation requires Playwright.\n"
                "Install with: pip install playwright && python -m playwright install chromium"
            )

        if cls._page is None:
            cls._playwright = sync_playwright().start()
            cls._browser = cls._playwright.chromium.launch(
                headless=False,  # Visible browser for user visibility
                args=[
                    "--disable-blink-features=AutomationControlled",  # Anti-detection
                ],
            )
            cls._context = cls._browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            cls._page = cls._context.new_page()

        return cls._page

    @classmethod
    def is_open(cls) -> bool:
        """Check if browser is currently open."""
        return cls._page is not None

    @classmethod
    def close(cls):
        """Close browser and cleanup resources."""
        if cls._context:
            try:
                cls._context.close()
            except Exception:
                pass
        if cls._browser:
            try:
                cls._browser.close()
            except Exception:
                pass
        if cls._playwright:
            try:
                cls._playwright.stop()
            except Exception:
                pass
        cls._page = None
        cls._context = None
        cls._browser = None
        cls._playwright = None


def _check_url_security(url: str) -> None:
    """Apply same security checks as web_fetch.

    Args:
        url: URL to validate

    Raises:
        ValueError: If URL fails security checks
    """
    from urllib.parse import urlparse

    from patchpal.tools.web_tools import _check_domain_allowed, _domain_limiter

    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    parsed = urlparse(url)
    if not parsed.hostname:
        raise ValueError(f"Invalid URL: cannot extract hostname from {url}")

    # Check domain restrictions (same as web_fetch)
    _check_domain_allowed(parsed.hostname)

    # Rate limiting (same as web_fetch)
    _domain_limiter.check_limit(parsed.hostname, config.WEB_RATE_LIMIT)


def browser_navigate(url: str, wait_until: str = "domcontentloaded") -> str:
    """Navigate browser to a URL.

    Opens a visible Chromium window if not already open. Browser stays open
    for subsequent browser_* operations, allowing interactive workflows.

    Security: Applies same domain filtering and rate limiting as web_fetch.

    Args:
        url: URL to visit (must start with http:// or https://)
        wait_until: When to consider navigation complete (domcontentloaded, load, or networkidle)

    Returns:
        Page title and URL confirmation

    Raises:
        ValueError: If URL invalid or security checks fail
    """
    _operation_limiter.check_limit(f"browser_navigate({url})")

    # Security checks (reuse web_fetch infrastructure)
    _check_url_security(url)

    # Permission check
    permission_manager = _get_permission_manager()
    if not permission_manager.request_permission(
        "browser_navigate",
        f"   ● Navigate browser to: {url}",
        pattern="browser",
    ):
        return "Operation cancelled by user."

    page = _BrowserState.get_page()

    # Navigate with timeout
    page.goto(url, wait_until=wait_until, timeout=30000)

    return f"✓ Navigated to: {page.title()}\nURL: {page.url}"


def browser_click(selector: str) -> str:
    """Click an element in the browser.

    Supports multiple selector types for flexibility:
    - CSS selector: "#submit-button", ".btn-primary", "button.login"
    - Text content: "text=Login", "text=Submit Form"
    - ARIA role: "role=button:Submit", "role=link:Home"

    Args:
        selector: Element selector (CSS, text=..., or role=...)

    Returns:
        Confirmation message with current URL

    Raises:
        ValueError: If browser not open or element not found
    """
    _operation_limiter.check_limit(f"browser_click({selector[:50]})")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    permission_manager = _get_permission_manager()
    if not permission_manager.request_permission(
        "browser_click",
        f"   ● Click element: {selector}",
        pattern="browser",
    ):
        return "Operation cancelled by user."

    page = _BrowserState.get_page()

    # Handle different selector types (OpenWorker pattern)
    try:
        if selector.startswith("text="):
            page.get_by_text(selector[5:], exact=False).first.click(timeout=10000)
        elif selector.startswith("role="):
            role_name = selector[5:]
            if ":" in role_name:
                role, name = role_name.split(":", 1)
                page.get_by_role(role.strip(), name=name.strip()).first.click(timeout=10000)
            else:
                page.get_by_role(role_name.strip()).first.click(timeout=10000)
        else:
            # CSS selector
            page.locator(selector).first.click(timeout=10000)
    except Exception as e:
        return f"✗ Failed to click '{selector}': {e}\nTip: Use browser_get_text() to see available elements"

    return f"✓ Clicked: {selector}\nCurrent URL: {page.url}"


def browser_fill(selector: str, text: str, clear: bool = True) -> str:
    """Fill a form field with text.

    Supports multiple selector types:
    - CSS selector: "#username", "input[name='email']"
    - Placeholder text: "placeholder=Enter email"
    - Label text: "label=Username"

    Args:
        selector: Field selector (CSS, placeholder=..., or label=...)
        text: Text to enter into the field
        clear: Whether to clear existing content first (default: True)

    Returns:
        Confirmation message

    Raises:
        ValueError: If browser not open or field not found
    """
    _operation_limiter.check_limit(f"browser_fill({selector[:50]})")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    permission_manager = _get_permission_manager()
    # Show truncated text in permission prompt
    text_display = text if len(text) <= 100 else text[:97] + "..."
    if not permission_manager.request_permission(
        "browser_fill",
        f"   ● Fill '{selector}' with: {text_display}",
        pattern="browser",
    ):
        return "Operation cancelled by user."

    page = _BrowserState.get_page()

    try:
        if selector.startswith("placeholder="):
            locator = page.get_by_placeholder(selector[12:]).first
        elif selector.startswith("label="):
            locator = page.get_by_label(selector[6:]).first
        else:
            # CSS selector
            locator = page.locator(selector).first

        if clear:
            locator.fill(text, timeout=10000)
        else:
            # Type without clearing (append)
            locator.type(text, timeout=10000)
    except Exception as e:
        return f"✗ Failed to fill '{selector}': {e}\nTip: Use browser_get_text() to see available form fields"

    return f"✓ Filled '{selector}'\nCurrent URL: {page.url}"


def browser_screenshot(path: str = "") -> str:
    """Take a full-page screenshot of the current browser page.

    Args:
        path: Where to save screenshot. If empty, saves to /tmp/patchpal_screenshot.png

    Returns:
        Path to saved screenshot file

    Raises:
        ValueError: If browser not open
    """
    _operation_limiter.check_limit("browser_screenshot")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    page = _BrowserState.get_page()

    # Default path if not specified
    if not path:
        path = "/tmp/patchpal_screenshot.png"

    save_path = Path(path).expanduser().resolve()
    save_path.parent.mkdir(parents=True, exist_ok=True)

    # Take full-page screenshot
    page.screenshot(path=str(save_path), full_page=True)

    return f"✓ Screenshot saved: {save_path}\nURL: {page.url}\nTitle: {page.title()}"


def browser_get_text(max_chars: int = 20000) -> str:
    """Get all visible text from the current browser page.

    Extracts rendered text content after JavaScript execution, unlike web_fetch
    which only gets static HTML. Useful for single-page applications and
    dynamically loaded content.

    Args:
        max_chars: Maximum characters to return (default: 20000)

    Returns:
        Page text content with title and URL

    Raises:
        ValueError: If browser not open
    """
    _operation_limiter.check_limit("browser_get_text")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    page = _BrowserState.get_page()

    # Extract text from body
    text = page.locator("body").inner_text(timeout=5000)

    # Clean up excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Truncate if too long
    truncated = False
    if len(text) > max_chars:
        text = text[:max_chars]
        truncated = True

    # Track URLs found in page (integrate with web_fetch's URL tracking)
    if not config.ALLOW_DYNAMIC_URLS:
        try:
            from patchpal.tools.web_tools import _url_tracker

            _url_tracker.add_urls_from_text(text)
        except Exception:
            pass  # Graceful degradation if web_tools not available

    result = f"Title: {page.title()}\nURL: {page.url}\n\n{text}"

    if truncated:
        result += f"\n\n[... text truncated at {max_chars} characters ...]"

    return result


def browser_wait(milliseconds: int = 1000, selector: str = "") -> str:
    """Wait for a duration or for an element to appear.

    Useful for waiting for dynamic content to load or animations to complete.

    Args:
        milliseconds: How long to wait (default: 1000ms, max: 30000ms)
        selector: Optional CSS selector to wait for. If provided, waits for element to appear.

    Returns:
        Confirmation message

    Raises:
        ValueError: If browser not open or timeout exceeded
    """
    _operation_limiter.check_limit("browser_wait")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    page = _BrowserState.get_page()

    # Cap wait time at 30 seconds
    wait_ms = max(100, min(int(milliseconds), 30000))

    try:
        if selector:
            # Wait for element to appear
            page.locator(selector).first.wait_for(timeout=wait_ms, state="visible")
            return f"✓ Element appeared: {selector}\nCurrent URL: {page.url}"
        else:
            # Simple duration wait
            page.wait_for_timeout(wait_ms)
            return f"✓ Waited {wait_ms}ms\nCurrent URL: {page.url}"
    except Exception as e:
        return f"✗ Wait timeout: {e}"


def browser_close() -> str:
    """Close the browser and cleanup resources.

    Closes the browser window and releases all associated resources.
    Safe to call even if browser is already closed.

    Returns:
        Confirmation message
    """
    if not _BrowserState.is_open():
        return "Browser already closed"

    _BrowserState.close()
    return "✓ Browser closed"


# Public API - functions available to agent
__all__ = [
    "browser_navigate",
    "browser_click",
    "browser_fill",
    "browser_screenshot",
    "browser_get_text",
    "browser_wait",
    "browser_close",
    "PLAYWRIGHT_AVAILABLE",
]
