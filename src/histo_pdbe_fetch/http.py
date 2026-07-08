"""Disk-cached HTTP GET with polite headers."""

from __future__ import annotations

import hashlib
from pathlib import Path

import requests

DEFAULT_CACHE_DIR = Path.home() / ".cache" / "histo_pdbe_fetch"
USER_AGENT = "histo-pdbe-fetch/0.1.0 (https://github.com/drchristhorpe/histo_pdbe_fetch)"


def _cache_path(cache_dir: Path, url: str) -> Path:
    """Derive a cache file path from URL via SHA256 hash."""
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    return cache_dir / url_hash


def cached_get(url: str, cache_dir: Path, refresh: bool) -> str:
    """Fetch URL with disk cache.

    Args:
        url: URL to fetch
        cache_dir: Directory for cache files (created if missing)
        refresh: If True, bypass cache and re-fetch

    Returns:
        Response text

    Raises:
        requests.HTTPError: On HTTP error status
        requests.RequestException: On network error
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = _cache_path(cache_dir, url)

    if not refresh and cache_file.exists():
        return cache_file.read_text(encoding="utf-8")

    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=30)
    response.raise_for_status()

    cache_file.write_text(response.text, encoding="utf-8")
    return response.text
