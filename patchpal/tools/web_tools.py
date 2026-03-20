"""Web tools (fetch, search)."""

import os
import unicodedata
from collections import defaultdict
from time import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from patchpal.config import config

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

from patchpal.tools.common import (
    WEB_HEADERS,
    _get_permission_manager,
    _operation_limiter,
    audit_logger,
    extract_text_from_docx,
    extract_text_from_pdf,
    extract_text_from_pptx,
)

# ============================================================================
# Security: Binary Detection via Magic Numbers
# ============================================================================

# Common file type signatures (magic numbers)
BINARY_MAGIC_NUMBERS = {
    b"\x7fELF": "ELF executable",
    b"MZ": "Windows executable (PE)",
    b"\x89PNG\r\n\x1a\n": "PNG image",
    b"GIF87a": "GIF image (87a)",
    b"GIF89a": "GIF image (89a)",
    b"\xff\xd8\xff": "JPEG image",
    b"PK\x03\x04": "ZIP archive",
    b"PK\x05\x06": "ZIP archive (empty)",
    b"PK\x07\x08": "ZIP archive (spanned)",
    b"Rar!\x1a\x07": "RAR archive",
    b"\x1f\x8b\x08": "GZIP archive",
    b"BM": "BMP image",
    b"RIFF": "RIFF container (AVI, WAV, WebP)",
    b"\x00\x00\x01\x00": "ICO image",
    b"\x49\x49\x2a\x00": "TIFF image (little-endian)",
    b"\x4d\x4d\x00\x2a": "TIFF image (big-endian)",
    b"\xca\xfe\xba\xbe": "Java class file / Mach-O (fat binary)",
    b"\xfe\xed\xfa\xce": "Mach-O executable (32-bit)",
    b"\xfe\xed\xfa\xcf": "Mach-O executable (64-bit)",
    b"\xcf\xfa\xed\xfe": "Mach-O executable (reverse byte order)",
}


def _detect_binary(content: bytes, content_type: str) -> tuple[bool, str | None]:
    """Detect binary content by magic numbers (more reliable than Content-Type).

    Args:
        content: First bytes of the downloaded content
        content_type: Content-Type header from server

    Returns:
        (is_binary, description) tuple
    """
    # Check magic numbers first (most reliable)
    for magic, description in BINARY_MAGIC_NUMBERS.items():
        if content.startswith(magic):
            return True, description

    # Fallback to Content-Type checking (can be spoofed, but still useful)
    binary_content_types = [
        "image/",
        "video/",
        "audio/",
        "application/zip",
        "application/x-zip",
        "application/x-rar",
        "application/x-tar",
        "application/x-gzip",
        "application/x-7z-compressed",
        "application/x-bzip",
        "application/x-bzip2",
        "application/x-executable",
        "application/x-sharedlib",
        "application/x-mach-binary",
        "application/vnd.ms-",  # Microsoft Office binary formats
        "application/octet-stream",
    ]

    content_type_lower = content_type.lower()
    for binary_type in binary_content_types:
        if binary_type in content_type_lower:
            return True, f"Content-Type: {content_type}"

    return False, None


# ============================================================================
# Security: Rate Limiting Per Domain
# ============================================================================


class DomainRateLimiter:
    """Rate limiter to prevent hammering domains."""

    def __init__(self):
        self.requests = defaultdict(list)  # domain -> [timestamps]

    def check_limit(self, domain: str, max_per_minute: int):
        """Check if domain rate limit has been exceeded.

        Args:
            domain: Domain name (e.g., "example.com")
            max_per_minute: Maximum requests per minute for this domain

        Raises:
            ValueError: If rate limit exceeded
        """
        now = time()

        # Remove requests older than 1 minute
        self.requests[domain] = [t for t in self.requests[domain] if now - t < 60]

        if len(self.requests[domain]) >= max_per_minute:
            raise ValueError(
                f"Rate limit exceeded for {domain}: {max_per_minute} requests/minute\n"
                f"This is a safety measure to prevent hammering websites.\n"
                f"Wait a moment or increase PATCHPAL_WEB_RATE_LIMIT."
            )

        self.requests[domain].append(now)


# Global rate limiter instance
_domain_limiter = DomainRateLimiter()


# ============================================================================
# Security: Domain Filtering
# ============================================================================


def _check_domain_allowed(hostname: str) -> None:
    """Check if domain is allowed based on allow/block lists.

    Args:
        hostname: Domain hostname (e.g., "docs.python.org")

    Raises:
        ValueError: If domain is not allowed
    """
    # Check if both allow and block lists are set (configuration error)
    if config.WEB_ALLOWED_DOMAINS and config.WEB_BLOCKED_DOMAINS:
        raise ValueError(
            "Configuration error: Cannot use both PATCHPAL_WEB_ALLOWED_DOMAINS "
            "and PATCHPAL_WEB_BLOCKED_DOMAINS at the same time.\n"
            "Choose one approach: either allowlist OR blocklist."
        )

    # Check blocked domains
    if config.WEB_BLOCKED_DOMAINS:
        blocked = [d.strip() for d in config.WEB_BLOCKED_DOMAINS.split(",")]
        for blocked_domain in blocked:
            # Support subdomain matching (docs.example.com matches example.com)
            # and subpath matching (example.com/internal matches example.com/internal)
            if hostname == blocked_domain or hostname.endswith("." + blocked_domain):
                raise ValueError(
                    f"Access to domain blocked: {hostname}\n"
                    f"Domain '{blocked_domain}' is in PATCHPAL_WEB_BLOCKED_DOMAINS.\n"
                    f"Remove from blocklist to allow access."
                )

    # Check allowed domains
    if config.WEB_ALLOWED_DOMAINS:
        allowed = [d.strip() for d in config.WEB_ALLOWED_DOMAINS.split(",")]
        is_allowed = False
        for allowed_domain in allowed:
            if hostname == allowed_domain or hostname.endswith("." + allowed_domain):
                is_allowed = True
                break

        if not is_allowed:
            raise ValueError(
                f"Access to domain not allowed: {hostname}\n"
                f"Domain not in PATCHPAL_WEB_ALLOWED_DOMAINS.\n"
                f"Allowed domains: {', '.join(allowed)}\n"
                f"Add '{hostname}' to allowlist or remove PATCHPAL_WEB_ALLOWED_DOMAINS to allow all."
            )


# ============================================================================
# Security: Homograph Attack Detection
# ============================================================================


def _contains_unicode_homographs(domain: str) -> bool:
    """Detect potential homograph attacks in domain names.

    Checks for mixed scripts (e.g., Latin + Cyrillic) which can be used
    to create visually similar but different domains:
    - amazon.com (legitimate)
    - аmazon.com (Cyrillic 'а', malicious)

    Args:
        domain: Domain name to check

    Returns:
        True if potential homograph attack detected
    """
    # Track which Unicode scripts appear in the domain
    scripts = set()

    for char in domain:
        if char.isalpha():
            # Determine the script (Latin, Cyrillic, Greek, etc.)
            try:
                script_name = unicodedata.name(char).split()[0]
                scripts.add(script_name)
            except ValueError:
                # Character doesn't have a Unicode name
                scripts.add("UNKNOWN")

    # If more than one script is used, it's suspicious
    # (Legitimate domains typically use a single script)
    return len(scripts) > 1


# ============================================================================
# Security: URL Context Tracking
# ============================================================================


class URLContextTracker:
    """Track URLs that have appeared in conversation context."""

    def __init__(self):
        self.seen_urls = set()

    def add_urls_from_text(self, text: str) -> None:
        """Extract and remember URLs from text.

        Args:
            text: Text that may contain URLs
        """
        # Simple URL extraction (http:// and https://)
        import re

        url_pattern = r"https?://[^\s<>\"\'\)]*"
        urls = re.findall(url_pattern, text)
        self.seen_urls.update(urls)

    def is_url_in_context(self, url: str) -> bool:
        """Check if URL has appeared in conversation context.

        Args:
            url: URL to check

        Returns:
            True if URL was seen in context
        """
        return url in self.seen_urls

    def clear(self) -> None:
        """Clear tracked URLs (useful for new sessions)."""
        self.seen_urls.clear()


# Global URL tracker (will be populated by agent if ALLOW_DYNAMIC_URLS=false)
_url_tracker = URLContextTracker()


def get_url_tracker() -> URLContextTracker:
    """Get the global URL tracker instance.

    This is used by the agent to track URLs from user messages and tool results.

    Returns:
        The global URLContextTracker instance
    """
    return _url_tracker


def reset_url_tracker() -> None:
    """Reset the URL tracker (useful for new sessions)."""
    _url_tracker.clear()


def web_fetch(url: str, extract_text: bool = True) -> str:
    """
    Fetch content from a URL and optionally extract readable text.

    Security features:
    - URL validation (must be in conversation context if ALLOW_DYNAMIC_URLS=false)
    - Domain filtering (allow/block lists)
    - Homograph attack detection
    - Rate limiting per domain
    - Binary file detection via magic numbers
    - Content size limits

    Args:
        url: The URL to fetch
        extract_text: If True, extract readable text from HTML/PDF (default: True)

    Returns:
        The fetched content (text extracted from HTML/PDF if extract_text=True)

    Raises:
        ValueError: If request fails, content is too large, or security checks fail
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   Fetch: {url}"
    if not permission_manager.request_permission("web_fetch", description):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"web_fetch({url[:50]}...)")

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        raise ValueError("URL must start with http:// or https://")

    # Parse URL to extract hostname
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname
        if not hostname:
            raise ValueError(f"Invalid URL: cannot extract hostname from {url}")
    except Exception as e:
        raise ValueError(f"Invalid URL format: {e}")

    # Security check 1: URL context validation (prevent data exfiltration)
    if not config.ALLOW_DYNAMIC_URLS:
        if not _url_tracker.is_url_in_context(url):
            raise ValueError(
                f"Security: URL not found in conversation context: {url}\n\n"
                f"For security, web_fetch can only access URLs that were:\n"
                f"- Explicitly provided by you in your messages\n"
                f"- Returned by web_search\n"
                f"- Returned by previous web_fetch calls\n"
                f"- Found in files read with read_file\n\n"
                f"This prevents data exfiltration via dynamically constructed URLs.\n"
                f"Set PATCHPAL_ALLOW_DYNAMIC_URLS=true to disable this check (not recommended)."
            )

    # Security check 2: Homograph attack detection
    if not config.ALLOW_UNICODE_DOMAINS and _contains_unicode_homographs(hostname):
        raise ValueError(
            f"Security: Potential homograph attack detected in domain: {hostname}\n\n"
            f"Domain contains mixed scripts (e.g., Latin + Cyrillic characters).\n"
            f"This can be used to create visually similar but different domains:\n"
            f"- amazon.com (legitimate)\n"
            f"- аmazon.com (Cyrillic 'а', potentially malicious)\n\n"
            f"Set PATCHPAL_ALLOW_UNICODE_DOMAINS=true to override (not recommended)."
        )

    # Security check 3: Domain filtering
    _check_domain_allowed(hostname)

    # Security check 4: Rate limiting
    _domain_limiter.check_limit(hostname, config.WEB_RATE_LIMIT)

    try:
        # Make request with timeout and browser-like headers
        response = requests.get(
            url,
            timeout=config.WEB_TIMEOUT,
            headers=WEB_HEADERS,
            stream=True,  # Stream to check size first
            allow_redirects=True,  # Follow redirects (including moved repos)
        )
        response.raise_for_status()

        # Check content size BEFORE downloading
        content_length = response.headers.get("Content-Length")
        if content_length and int(content_length) > config.MAX_WEB_SIZE:
            raise ValueError(
                f"Content too large: {int(content_length):,} bytes "
                f"(max {config.MAX_WEB_SIZE:,} bytes)"
            )

        # Read content with size limit
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            content += chunk
            if len(content) > config.MAX_WEB_SIZE:
                raise ValueError(f"Content exceeds size limit ({config.MAX_WEB_SIZE:,} bytes)")

        # Get content type
        content_type = response.headers.get("Content-Type", "").lower()

        # Security check 5: Binary detection via magic numbers (defense in depth)
        # Check first few KB for magic numbers
        is_binary, binary_type = _detect_binary(content[:8192], content_type)
        if is_binary:
            raise ValueError(
                f"[Binary file detected: {binary_type}]\n\n"
                f"Content-Type: {content_type}\n"
                f"URL: {url}\n\n"
                f"web_fetch only supports text extraction from:\n"
                f"- HTML pages\n"
                f"- PDF documents\n"
                f"- DOCX documents\n"
                f"- PPTX presentations\n"
                f"- Plain text files (JSON, XML, CSV, etc.)\n\n"
                f"This file appears to be a binary format and cannot be processed."
            )

        # Extract text based on content type
        if extract_text:
            if "pdf" in content_type:
                # Extract text from PDF
                try:
                    text_content = extract_text_from_pdf(content, source=url)
                except ValueError as e:
                    # Return helpful error message if extraction fails
                    text_content = f"[{e}]"
            elif "wordprocessingml" in content_type or "msword" in content_type:
                # Extract text from DOCX (or DOC if saved as docx)
                try:
                    text_content = extract_text_from_docx(content, source=url)
                except ValueError as e:
                    text_content = f"[{e}]"
            elif "presentationml" in content_type or "ms-powerpoint" in content_type:
                # Extract text from PPTX (or PPT if saved as pptx)
                try:
                    text_content = extract_text_from_pptx(content, source=url)
                except ValueError as e:
                    text_content = f"[{e}]"
            elif "html" in content_type:
                # Extract text from HTML
                text_content = content.decode(response.encoding or "utf-8", errors="replace")
                soup = BeautifulSoup(text_content, "html.parser")

                # Remove script and style elements
                for element in soup(["script", "style", "nav", "footer", "header"]):
                    element.decompose()

                # Get text
                text = soup.get_text()

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text_content = "\n".join(chunk for chunk in chunks if chunk)
            else:
                # Assume it's text-based (JSON, XML, CSV, etc.)
                # Try to decode as text
                try:
                    text_content = content.decode(response.encoding or "utf-8", errors="replace")
                except Exception:
                    raise ValueError(
                        f"Unable to decode content as text\n"
                        f"Content-Type: {content_type}\n"
                        f"URL: {url}"
                    )
        else:
            # No text extraction - just decode
            text_content = content.decode(response.encoding or "utf-8", errors="replace")

        # Track this URL for future validation (if URL context tracking is enabled)
        if not config.ALLOW_DYNAMIC_URLS:
            _url_tracker.add_urls_from_text(text_content)

        # Note: Output truncation is handled by universal MAX_TOOL_OUTPUT_CHARS limit in agent.py
        audit_logger.info(f"WEB_FETCH: {url} ({len(text_content)} chars)")
        return text_content

    except requests.Timeout:
        raise ValueError(f"Request timed out after {config.WEB_TIMEOUT} seconds")
    except requests.RequestException as e:
        raise ValueError(f"Failed to fetch URL: {e}")
    except Exception as e:
        raise ValueError(f"Error processing content: {e}")


def web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web using DuckDuckGo and return results.

    Args:
        query: The search query
        max_results: Maximum number of results to return (default: 5, max: 10)

    Returns:
        Formatted search results with titles, URLs, and snippets

    Raises:
        ValueError: If search fails
    """
    # Check permission before proceeding
    permission_manager = _get_permission_manager()
    description = f"   Search: {query}"
    if not permission_manager.request_permission("web_search", description):
        return "Operation cancelled by user."

    _operation_limiter.check_limit(f"web_search({query[:30]}...)")

    # Limit max_results
    max_results = min(max_results, 10)

    try:
        # Determine SSL verification setting
        # Priority: PATCHPAL_VERIFY_SSL env var > SSL_CERT_FILE > REQUESTS_CA_BUNDLE > default True
        verify_ssl = config.VERIFY_SSL
        if verify_ssl is not None:
            # User explicitly set PATCHPAL_VERIFY_SSL
            if verify_ssl.lower() in ("false", "0", "no"):
                verify = False
            elif verify_ssl.lower() in ("true", "1", "yes"):
                verify = True
            else:
                # Treat as path to CA bundle
                verify = verify_ssl
        else:
            # Use SSL_CERT_FILE or REQUESTS_CA_BUNDLE if set (for corporate environments)
            verify = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE") or True

        # Perform search using DuckDuckGo
        with DDGS(verify=verify) as ddgs:
            results = list(ddgs.text(query, max_results=max_results))

        if not results:
            audit_logger.info(f"WEB_SEARCH: {query} - No results")
            return f"No search results found for: {query}"

        # Format results
        formatted_results = [f"Search results for: {query}\n"]
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            url = result.get("href", "No URL")
            snippet = result.get("body", "No description")

            formatted_results.append(f"\n{i}. {title}\n   URL: {url}\n   {snippet}")

            # Track URLs from search results (for URL context validation)
            if not config.ALLOW_DYNAMIC_URLS:
                _url_tracker.add_urls_from_text(url)

        output = "\n".join(formatted_results)
        audit_logger.info(f"WEB_SEARCH: {query} - Found {len(results)} results")
        return output

    except Exception as e:
        error_msg = str(e)

        # Provide helpful error messages for common issues
        if "CERTIFICATE_VERIFY_FAILED" in error_msg or "TLS handshake failed" in error_msg:
            return (
                "Web search unavailable: SSL certificate verification failed.\n"
                "This may be due to:\n"
                "- Corporate proxy/firewall blocking requests\n"
                "- Network configuration issues\n"
                "- VPN interference\n\n"
                "Consider using web_fetch with a specific URL if you have one."
            )
        elif "RuntimeError" in error_msg or "error sending request" in error_msg:
            return (
                "Web search unavailable: Network connection failed.\n"
                "Please check your internet connection and try again."
            )
        else:
            raise ValueError(f"Web search failed: {e}")
