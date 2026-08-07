"""Browser automation tools using Playwright.

Provides interactive browser capabilities for tasks requiring JavaScript execution,
form interaction, or visual rendering that web_fetch cannot handle.

Optional dependency: Install with `pip install patchpal[browser]` and run
`python -m playwright install chromium` to use these tools.
"""

import os
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


def _dismiss_modals(page: Page):
    """Automatically dismiss common modal overlays that block interaction.

    Many sites (Zillow, real estate sites, news sites) show modals for:
    - Login prompts
    - Newsletter signups
    - Cookie notices
    - App download prompts
    - Location permissions

    This attempts to close them using common close button selectors.

    Args:
        page: Playwright page object
    """
    # Common selectors for modal close buttons
    # Ordered by specificity (most specific first)
    close_selectors = [
        # ARIA labels (most semantic)
        'button[aria-label*="close" i]',
        'button[aria-label*="dismiss" i]',
        '[role="button"][aria-label*="close" i]',
        # Common class names
        ".modal-close",
        ".close-button",
        ".dismiss-button",
        ".popup-close",
        '[class*="close"][class*="button"]',
        '[class*="Close"][class*="Button"]',
        # SVG/icon close buttons
        'button svg[class*="close"]',
        'button [class*="close-icon"]',
        # X buttons
        'button:has-text("×")',
        'button:has-text("✕")',
        '[aria-label="Close"]',
        # Generic buttons in modals/dialogs
        '[role="dialog"] button[class*="close"]',
        '.modal button[class*="close"]',
        # Data attributes
        '[data-testid*="close"]',
        '[data-testid*="dismiss"]',
    ]

    try:
        for selector in close_selectors:
            try:
                # Check if element exists and is visible
                element = page.locator(selector).first
                if element.is_visible(timeout=100):  # Quick check
                    element.click(timeout=500)
                    # Wait briefly for modal to close
                    page.wait_for_timeout(300)
                    # Try to close more modals (some sites have multiple)
                    continue
            except Exception:
                # Element doesn't exist or not clickable, try next selector
                continue
    except Exception:
        # Silently fail if modal dismissal has issues
        pass


# Apply nest_asyncio if available to prevent event loop conflicts
# This must be done EARLY before any Playwright operations
# nest_asyncio patches asyncio globally to allow nested event loops
_NEST_ASYNCIO_APPLIED = False
try:
    import nest_asyncio

    nest_asyncio.apply()
    _NEST_ASYNCIO_APPLIED = True
except ImportError:
    # nest_asyncio not installed, may cause issues in async contexts
    pass
except Exception:
    # Silently ignore if nest_asyncio fails to apply
    pass


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
    _current_frame: Optional[Page] = None  # Current frame context (None = main page)

    @classmethod
    def get_page(cls) -> Page:
        """Get or create browser page.

        Returns:
            Playwright Page object (or Frame if frame is selected)

        Raises:
            ValueError: If Playwright not installed
            RuntimeError: If browser initialization fails
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise ValueError(
                "Browser automation requires Playwright.\n"
                "Install with: pip install playwright && python -m playwright install chromium"
            )

        if cls._page is None:
            try:
                # Try to start playwright - this may fail with asyncio errors
                cls._playwright = sync_playwright().start()
            except RuntimeError as e:
                error_msg = str(e)
                if "asyncio.run() cannot be called from a running event loop" in error_msg:
                    # The current event loop is in a state that Playwright's sync
                    # API cannot use (typically because it is running and not
                    # patched for re-entrancy). Re-apply nest_asyncio to the
                    # *current* loop and retry. This recovers cleanly instead of
                    # requiring a full PatchPal restart.
                    try:
                        import nest_asyncio

                        nest_asyncio.apply()
                    except Exception:
                        pass
                    try:
                        cls._playwright = sync_playwright().start()
                    except RuntimeError:
                        # Still failing - provide helpful error
                        raise RuntimeError(
                            "Browser automation failed due to event loop conflict.\n"
                            "This is a known issue with Playwright in certain environments.\n"
                            "Workarounds:\n"
                            "1. Close the browser and restart PatchPal\n"
                            "2. Use web_fetch for static pages instead of browser tools\n"
                            "3. Try: pip install --upgrade nest-asyncio playwright"
                        ) from e
                raise

            # Resolve SSL policy consistently with web_fetch / web_search.
            #
            # IMPORTANT: Unlike `requests` (web_fetch/web_search), the Chromium
            # process launched by Playwright does NOT honor NODE_EXTRA_CA_CERTS,
            # SSL_CERT_FILE, or REQUESTS_CA_BUNDLE for *page navigation* TLS.
            # NODE_EXTRA_CA_CERTS only affects Node's own HTTPS (used when
            # downloading browser binaries), not the launched browser. Chromium
            # validates page certificates against the OS/NSS trust store instead.
            # (Verified empirically: pointing NODE_EXTRA_CA_CERTS at a server's
            # own cert still yields net::ERR_CERT_AUTHORITY_INVALID.)
            #
            # Therefore, to trust a corporate/self-signed CA in the browser you
            # must install it into the OS trust store out-of-band, e.g. on Linux:
            #   certutil -d sql:$HOME/.pki/nssdb -A -t "C,," -n corp-ca \
            #            -i /path/to/corporate-ca.pem
            #
            # The only knob we can meaningfully control here is whether to bypass
            # certificate validation entirely:
            #   - PATCHPAL_VERIFY_SSL=false            -> accept ANY cert
            #   - PATCHPAL_BROWSER_IGNORE_HTTPS_ERRORS=true -> accept ANY cert
            #   - otherwise                            -> validate against OS trust store
            ignore_https_errors = False
            try:
                from patchpal.tools.web_tools import resolve_ssl_verify

                verify, _ca_bundle = resolve_ssl_verify()
                if verify is False:
                    # User explicitly opted out of verification
                    ignore_https_errors = True
            except Exception:
                # If policy resolution fails for any reason, fall back to normal
                # verification rather than silently accepting bad certs.
                ignore_https_errors = False

            # Dedicated opt-out for the browser (corporate proxies whose CA is
            # not in the OS trust store). This is the browser equivalent of
            # requests' verify=False and does NOT affect web_fetch/web_search.
            if os.getenv("PATCHPAL_BROWSER_IGNORE_HTTPS_ERRORS", "").lower() in (
                "true",
                "1",
                "yes",
            ):
                ignore_https_errors = True

            # Use persistent context to maintain cookies, localStorage, and browsing
            # history between sessions. This makes automation less detectable and
            # allows authenticated sessions to persist.
            from pathlib import Path

            user_data_dir = Path.home() / ".patchpal" / "browser_profile"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            try:
                cls._context = cls._playwright.chromium.launch_persistent_context(
                    str(user_data_dir),
                    headless=False,  # Visible browser for user visibility
                    args=[
                        "--disable-blink-features=AutomationControlled",  # Anti-detection
                    ],
                    viewport={"width": 1280, "height": 900},
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    ignore_https_errors=ignore_https_errors,
                )
                # With persistent context, we get pages directly (no separate browser object)
                cls._browser = None
                cls._page = cls._context.pages[0] if cls._context.pages else cls._context.new_page()
            except Exception:
                # Cleanup on failure
                cls.close(silent=True)
                raise

        return cls._page

    @classmethod
    def get_context(cls) -> Page:
        """Get the current context (frame or page).

        Returns the current frame if one is selected, otherwise returns the main page.
        This is what browser tools should use for operations.

        Returns:
            Playwright Page or Frame object
        """
        if cls._current_frame is not None:
            return cls._current_frame
        return cls.get_page()

    @classmethod
    def set_frame(cls, frame: Optional[Page]) -> None:
        """Set the current frame context.

        Args:
            frame: Frame to switch to, or None to switch back to main page
        """
        cls._current_frame = frame

    @classmethod
    def is_open(cls) -> bool:
        """Check if browser is currently open."""
        return cls._page is not None

    @classmethod
    def close(cls, silent: bool = False):
        """Close browser and cleanup resources.

        Args:
            silent: If True, suppress all output (used during atexit cleanup)
        """
        # Suppress all stderr during close to prevent asyncio error messages
        import io
        import sys

        # Save stderr
        original_stderr = sys.stderr

        try:
            # Redirect stderr to suppress error messages during cleanup
            if silent:
                sys.stderr = io.StringIO()

            if cls._context:
                try:
                    cls._context.close()
                except Exception:
                    pass
            # No separate browser object with persistent context
            if cls._playwright:
                try:
                    cls._playwright.stop()
                except (Exception, RuntimeError):
                    # RuntimeError can happen during shutdown when event loop is closing
                    # Suppress all errors during cleanup, especially asyncio errors
                    pass

                # NOTE: Do NOT manipulate the asyncio event loop here (e.g.
                # asyncio.set_event_loop(asyncio.new_event_loop())). Doing so
                # replaces the loop that nest_asyncio patched at import time with
                # a fresh, unpatched loop. The next sync_playwright().start()
                # then fails with "asyncio.run() cannot be called from a running
                # event loop" on every subsequent call. Playwright's stop()
                # already cleans up its own loop.
                #
                # However, sync_playwright().start() DOES install its own event
                # loop as the thread's current loop while running. After stop(),
                # that loop is closed but may remain registered as the current
                # loop, which breaks the NEXT asyncio.run() call made by other
                # libraries (notably prompt_toolkit's session.prompt(), which is
                # how PatchPal reads the "You:" prompt). The symptom is a flood
                # of "asyncio.run() cannot be called from a running event loop".
                #
                # Fix: ensure the thread has a fresh, OPEN, nest_asyncio-patched
                # loop registered after Playwright tears down. We create a new
                # loop (the previous one is closed/unusable) and re-apply
                # nest_asyncio so re-entrant asyncio.run() works again.
                try:
                    import asyncio as _asyncio

                    _needs_new_loop = True
                    try:
                        _existing = _asyncio.get_event_loop()
                        if _existing is not None and not _existing.is_closed():
                            _needs_new_loop = False
                    except Exception:
                        _needs_new_loop = True

                    if _needs_new_loop:
                        _asyncio.set_event_loop(_asyncio.new_event_loop())

                    try:
                        import nest_asyncio as _nest

                        _nest.apply()
                    except Exception:
                        pass
                except Exception:
                    pass

            cls._page = None
            cls._context = None
            cls._browser = None
            cls._playwright = None
        finally:
            # Always restore stderr
            sys.stderr = original_stderr


# Register cleanup handler to close browser on exit (prevent asyncio errors on Ctrl-C)
# NOTE: Disabled because it may cause asyncio errors during cleanup
# The browser will be closed explicitly by browser_close() or when permission is denied
# def _cleanup_browser():
#     """Cleanup handler called at exit to ensure browser is closed."""
#     try:
#         _BrowserState.close(silent=True)
#     except Exception:
#         # Suppress all errors during exit cleanup
#         pass
#
#
# atexit.register(_cleanup_browser)


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
        # User denied permission - close browser to prevent retry issues
        # This ensures a clean state for the next operation
        if _BrowserState.is_open():
            _BrowserState.close(silent=True)
        return "Operation cancelled by user."

    try:
        page = _BrowserState.get_page()
    except RuntimeError as e:
        # If browser initialization fails, make sure it's fully closed
        _BrowserState.close(silent=True)
        error_msg = str(e)
        if "asyncio.run() cannot be called from a running event loop" in error_msg:
            return (
                "✗ Browser automation error: Event loop conflict.\n"
                "Browser has been closed. Please restart PatchPal to use browser tools.\n"
                "Alternative: Use web_fetch for static pages instead."
            )
        raise

    try:
        # Navigate with timeout
        page.goto(url, wait_until=wait_until, timeout=30000)

        # Reset frame context when navigating to new page
        _BrowserState.set_frame(None)

        # Wait a moment for any modals to appear
        page.wait_for_timeout(1000)

        # Auto-dismiss any modal overlays
        _dismiss_modals(page)

        return f"✓ Navigated to: {page.title()}\nURL: {page.url}"
    except Exception as e:
        error_msg = str(e)
        # Check for specific errors that might need browser restart
        if "asyncio" in error_msg.lower() or "event loop" in error_msg.lower():
            _BrowserState.close(silent=True)
            return (
                "✗ Browser error occurred. Browser has been closed.\n"
                "You may need to restart PatchPal to use browser tools again."
            )
        # For other navigation errors, leave browser open
        return f"✗ Navigation failed: {error_msg}"


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

    page = _BrowserState.get_context()  # Use current frame context

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

    # Check for modals that might appear after clicking
    try:
        page.wait_for_timeout(500)
        _dismiss_modals(page)
    except Exception:
        pass

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

    page = _BrowserState.get_context()  # Use current frame context

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

    Note: Screenshots are always taken of the entire page, not individual frames.
    If you've switched to a frame, the screenshot will still capture the whole page.

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

    # Always use main page for screenshots (frames don't have screenshot method)
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

    Note: This extracts only visible text, not HTML structure. To see HTML with
    element IDs/names for form interaction, use browser_get_html() instead.

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

    page = _BrowserState.get_context()  # Use current frame context

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


def browser_get_html(max_chars: int = 50000) -> str:
    """Get the HTML source code from the current browser page or frame.

    Extracts the raw HTML, which is useful for finding element IDs, names, and
    attributes needed for form interaction. Unlike browser_get_text(), this shows
    the actual HTML structure with <input>, <select>, and other form elements.

    Particularly useful for sites with complex forms or framesets where you need
    to identify specific field names or IDs.

    Args:
        max_chars: Maximum characters to return (default: 50000)

    Returns:
        HTML source code with title and URL

    Raises:
        ValueError: If browser not open
    """
    _operation_limiter.check_limit("browser_get_html")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first to open a page.")

    page = _BrowserState.get_context()  # Use current frame context

    # Get HTML content
    try:
        html = page.content()
    except Exception as e:
        return f"✗ Failed to get HTML: {e}"

    # Truncate if too long
    truncated = False
    if len(html) > max_chars:
        html = html[:max_chars]
        truncated = True

    result = f"Title: {page.title()}\nURL: {page.url}\n\nHTML Content:\n{html}"

    if truncated:
        result += f"\n\n[... HTML truncated at {max_chars} characters ...]"

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

    page = _BrowserState.get_context()  # Use current frame context

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


def browser_dismiss_modals() -> str:
    """Manually dismiss modal overlays blocking interaction.

    Many sites show modal popups (login prompts, newsletter signups, cookie notices,
    app download prompts) that block clicks and form interactions. This tool attempts
    to close them automatically.

    browser_navigate() and browser_click() already try to auto-dismiss modals, but
    use this tool if you still see modals blocking your actions.

    Returns:
        Confirmation message

    Raises:
        ValueError: If browser not open
    """
    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first.")

    page = _BrowserState.get_context()
    _dismiss_modals(page)
    return "✓ Attempted to dismiss modals. Check browser window to verify."


def browser_list_frames() -> str:
    """List all frames/iframes in the current page.

    Many older government and enterprise sites use framesets or iframes to organize
    content. This tool lists all available frames with their names, URLs, and indices,
    which you can use with browser_switch_frame() to interact with content inside frames.

    Returns:
        Formatted list of frames with indices, names, and URLs

    Raises:
        ValueError: If browser not open
    """
    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first.")

    page = _BrowserState.get_page()  # Always use main page to list frames
    frames = page.frames

    if len(frames) <= 1:
        return "✓ No frames found. Page uses standard layout (not framesets/iframes)."

    result = f"✓ Found {len(frames)} frame(s):\n\n"
    for i, frame in enumerate(frames):
        name = frame.name or "(unnamed)"
        url = frame.url or "(no URL)"
        is_main = " [MAIN]" if i == 0 else ""
        result += f"  [{i}] {name}{is_main}\n      URL: {url}\n\n"

    result += (
        "To interact with content in a frame, use:\n"
        "  browser_switch_frame(index) - switch by index number\n"
        "  browser_switch_frame(name='framename') - switch by frame name\n"
        "  browser_switch_frame() - return to main page"
    )

    return result


def browser_switch_frame(index: Optional[int] = None, name: Optional[str] = None) -> str:
    """Switch to a frame/iframe for interaction.

    Many sites (especially older government/enterprise sites) use framesets or iframes.
    Normal browser_click(), browser_fill(), etc. only work in the current frame context.
    Use this tool to switch to a specific frame before interacting with its content.

    After switching, all subsequent browser operations will target that frame until you
    switch back to the main page or to another frame.

    Args:
        index: Frame index from browser_list_frames() (0 is main page)
        name: Frame name attribute (alternative to index)

    Returns:
        Confirmation message with frame details

    Raises:
        ValueError: If browser not open, or both/neither index and name specified

    Examples:
        browser_switch_frame(index=1)  # Switch to first frame
        browser_switch_frame(name='content')  # Switch to frame named 'content'
        browser_switch_frame()  # Return to main page (index=0)
    """
    _operation_limiter.check_limit("browser_switch_frame")

    if not _BrowserState.is_open():
        raise ValueError("Browser not open. Use browser_navigate(url) first.")

    # Handle parameter validation
    if index is not None and name is not None:
        raise ValueError("Specify either 'index' or 'name', not both.")

    page = _BrowserState.get_page()  # Always work from main page
    frames = page.frames

    # Default to main page if no arguments
    if index is None and name is None:
        index = 0

    try:
        if name is not None:
            # Find frame by name
            target_frame = None
            for i, frame in enumerate(frames):
                if frame.name == name:
                    target_frame = frame
                    index = i
                    break
            if target_frame is None:
                available = [f.name or "(unnamed)" for f in frames]
                return f"✗ Frame '{name}' not found. Available frames: {', '.join(available)}"
        else:
            # Use index
            if index < 0 or index >= len(frames):
                return f"✗ Invalid frame index {index}. Valid range: 0-{len(frames) - 1}\nUse browser_list_frames() to see available frames."
            target_frame = frames[index]

        # Switch context
        if index == 0:
            # Main page
            _BrowserState.set_frame(None)
            return f"✓ Switched to main page\nURL: {page.url}"
        else:
            # Frame
            _BrowserState.set_frame(target_frame)
            frame_name = target_frame.name or "(unnamed)"
            frame_url = target_frame.url or "(no URL)"
            return f"✓ Switched to frame [{index}] {frame_name}\nFrame URL: {frame_url}\n\nYou can now use browser_click(), browser_fill(), etc. to interact with this frame."

    except Exception as e:
        return f"✗ Failed to switch frame: {e}"


# Public API - functions available to agent
__all__ = [
    "browser_navigate",
    "browser_click",
    "browser_fill",
    "browser_screenshot",
    "browser_get_text",
    "browser_get_html",
    "browser_wait",
    "browser_dismiss_modals",
    "browser_list_frames",
    "browser_switch_frame",
    "browser_close",
    "PLAYWRIGHT_AVAILABLE",
]
