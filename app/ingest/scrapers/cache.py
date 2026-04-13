"""Caching utility for scrapers to avoid repeated network requests during development."""

import hashlib
import os
import time
from pathlib import Path
from typing import Optional


# Default cache directory (relative to project root)
DEFAULT_CACHE_DIR = ".cache"

# Environment variable to control caching
USE_CACHE_ENV = "USE_CACHE"

# Max age for cached files (hours). After this, treat as miss and refetch.
# Set CACHE_MAX_AGE_HOURS=0 to disable TTL (cache forever while USE_CACHE=1).
# Stale RSS/HTML snapshots otherwise cause "0 results" when dates fall outside HOURS_BACK.
CACHE_MAX_AGE_HOURS_ENV = "CACHE_MAX_AGE_HOURS"
_DEFAULT_MAX_AGE_HOURS = 6.0


def is_cache_enabled() -> bool:
    """Check if caching is enabled via environment variable."""
    return os.environ.get(USE_CACHE_ENV, "1") == "1"


def _max_cache_age_seconds() -> Optional[float]:
    """Return max cache age in seconds, or None if TTL is disabled."""
    raw = os.environ.get(CACHE_MAX_AGE_HOURS_ENV, str(_DEFAULT_MAX_AGE_HOURS))
    try:
        hours = float(raw)
    except ValueError:
        hours = _DEFAULT_MAX_AGE_HOURS
    if hours <= 0:
        return None
    return hours * 3600.0


def get_cache_dir() -> Path:
    """Get the cache directory path, creating it if necessary."""
    cache_dir = Path(DEFAULT_CACHE_DIR)
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


def get_cache_key(url: str, suffix: str = "") -> str:
    """
    Generate a cache key from a URL.
    
    Args:
        url: The URL to hash
        suffix: Optional suffix to add (e.g., 'html', 'xml', 'vtt')
    
    Returns:
        MD5 hash of the URL with optional suffix
    """
    key = hashlib.md5(url.encode()).hexdigest()
    if suffix:
        return f"{key}.{suffix}"
    return key


def get_cached(url: str, suffix: str = "") -> Optional[str]:
    """
    Get cached content for a URL if it exists and caching is enabled.
    
    Args:
        url: The URL to look up
        suffix: File suffix (e.g., 'html', 'xml', 'vtt')
    
    Returns:
        Cached content as string, or None if not cached or caching disabled
    """
    if not is_cache_enabled():
        return None
    
    cache_path = get_cache_dir() / get_cache_key(url, suffix)
    
    if cache_path.exists():
        max_age = _max_cache_age_seconds()
        if max_age is not None:
            age = time.time() - cache_path.stat().st_mtime
            if age > max_age:
                print(f"[CACHE STALE {age/3600:.1f}h old] {url[:50]}...")
                return None
        print(f"[CACHE HIT] {url[:50]}...")
        return cache_path.read_text(encoding='utf-8')
    
    return None


def read_cached_ignore_ttl(url: str, suffix: str = "") -> Optional[str]:
    """
    Read cached file if it exists, without applying CACHE_MAX_AGE_HOURS.

    Use when reusing stored data avoids expensive or rate-limited upstream calls
    (e.g. skip yt-dlp when a transcript ``.vtt`` is already on disk).
    """
    if not is_cache_enabled():
        return None
    cache_path = get_cache_dir() / get_cache_key(url, suffix)
    if not cache_path.exists():
        return None
    return cache_path.read_text(encoding="utf-8")


def set_cached(url: str, content: str, suffix: str = "") -> None:
    """
    Cache content for a URL.
    
    Args:
        url: The URL to cache
        content: The content to cache
        suffix: File suffix (e.g., 'html', 'xml', 'vtt')
    """
    if not is_cache_enabled():
        return
    
    cache_path = get_cache_dir() / get_cache_key(url, suffix)
    cache_path.write_text(content, encoding='utf-8')
    print(f"[CACHE SAVE] {url[:50]}...")


def clear_cache() -> int:
    """
    Clear all cached files.
    
    Returns:
        Number of files deleted
    """
    cache_dir = get_cache_dir()
    count = 0
    for file in cache_dir.glob("*"):
        if file.is_file():
            file.unlink()
            count += 1
    print(f"[CACHE CLEARED] Removed {count} files")
    return count
