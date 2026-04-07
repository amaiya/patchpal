"""
Simple cache management for background automation jobs.

Provides JSON-based caching with deduplication and expiration support.
Useful for tracking seen items (Reddit posts, LinkedIn profiles, etc.).
"""

import json
import time
from pathlib import Path
from typing import Any, Optional, Set


def _get_cache_dir() -> Path:
    """Get the cache directory path."""
    cache_dir = Path.home() / ".patchpal" / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def get(key: str, default: Any = None) -> Any:
    """
    Get a value from cache.

    Args:
        key: Cache key (alphanumeric, dashes, underscores)
        default: Default value if key doesn't exist

    Returns:
        Cached value or default

    Example:
        >>> from patchpal.cache import get
        >>> seen_posts = get('reddit_seen', [])
    """
    cache_file = _get_cache_dir() / f"{key}.json"

    if not cache_file.exists():
        return default

    try:
        data = json.loads(cache_file.read_text())

        # Check expiration
        if isinstance(data, dict) and "_expires_at" in data:
            if time.time() > data["_expires_at"]:
                cache_file.unlink()
                return default
            return data.get("_value", default)

        return data
    except (json.JSONDecodeError, OSError):
        return default


def set(key: str, value: Any, ttl: Optional[int] = None) -> None:
    """
    Set a value in cache.

    Args:
        key: Cache key (alphanumeric, dashes, underscores)
        value: Value to cache (must be JSON-serializable)
        ttl: Time-to-live in seconds (optional)

    Example:
        >>> from patchpal.cache import set
        >>> set('reddit_seen', ['post1', 'post2'])
        >>> set('temp_data', {'count': 5}, ttl=3600)  # Expires in 1 hour
    """
    cache_file = _get_cache_dir() / f"{key}.json"

    if ttl:
        data = {"_value": value, "_expires_at": time.time() + ttl}
    else:
        data = value

    cache_file.write_text(json.dumps(data, indent=2))


def clear(key: Optional[str] = None) -> None:
    """
    Clear cache entries.

    Args:
        key: Specific key to clear, or None to clear all

    Example:
        >>> from patchpal.cache import clear
        >>> clear('reddit_seen')  # Clear specific key
        >>> clear()  # Clear all cache
    """
    cache_dir = _get_cache_dir()

    if key:
        cache_file = cache_dir / f"{key}.json"
        if cache_file.exists():
            cache_file.unlink()
    else:
        # Clear all cache files
        for cache_file in cache_dir.glob("*.json"):
            cache_file.unlink()


def add_to_set(key: str, *items: str) -> Set[str]:
    """
    Add items to a cached set (for deduplication).

    Args:
        key: Cache key
        items: Items to add

    Returns:
        Updated set

    Example:
        >>> from patchpal.cache import add_to_set, get_set
        >>> add_to_set('seen_posts', 'post123', 'post456')
        >>> 'post123' in get_set('seen_posts')
        True
    """
    current = get(key, [])
    if not isinstance(current, list):
        current = []

    current_set = set(current)
    current_set.update(items)

    updated = list(current_set)
    set(key, updated)

    return current_set


def get_set(key: str) -> Set[str]:
    """
    Get a cached set.

    Args:
        key: Cache key

    Returns:
        Set of items

    Example:
        >>> from patchpal.cache import get_set
        >>> seen = get_set('seen_posts')
        >>> if 'post123' not in seen:
        ...     print("New post!")
    """
    items = get(key, [])
    if not isinstance(items, list):
        return set()
    return set(items)


def is_duplicate(key: str, item: str) -> bool:
    """
    Check if an item has been seen before.

    Args:
        key: Cache key (e.g., 'reddit_seen')
        item: Item to check (e.g., post ID)

    Returns:
        True if item was seen before, False if new

    Example:
        >>> from patchpal.cache import is_duplicate, add_to_set
        >>> if not is_duplicate('reddit_seen', 'post123'):
        ...     print("New post!")
        ...     add_to_set('reddit_seen', 'post123')
    """
    return item in get_set(key)


def get_stats() -> dict:
    """
    Get cache statistics.

    Returns:
        Dictionary with cache stats

    Example:
        >>> from patchpal.cache import get_stats
        >>> stats = get_stats()
        >>> print(f"Cache entries: {stats['count']}")
    """
    cache_dir = _get_cache_dir()
    cache_files = list(cache_dir.glob("*.json"))

    total_size = sum(f.stat().st_size for f in cache_files)

    return {
        "count": len(cache_files),
        "size_bytes": total_size,
        "size_mb": round(total_size / 1024 / 1024, 2),
        "directory": str(cache_dir),
    }
