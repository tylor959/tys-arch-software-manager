"""TTL cache for expensive operations — package lists, search results, etc."""

from __future__ import annotations

import time
from typing import Any

from asm.core.logger import get_logger

_log = get_logger("cache")

# TTLs in seconds
CACHE_TTL_INSTALLED = 60
CACHE_TTL_SEARCH = 300  # 5 minutes

_cache: dict[str, tuple[Any, float]] = {}


def get(key: str, ttl: int) -> Any | None:
    """Return cached value if present and not expired."""
    if key not in _cache:
        return None
    value, expires = _cache[key]
    if time.monotonic() > expires:
        del _cache[key]
        return None
    return value


def set_(key: str, value: Any, ttl: int) -> None:
    """Store value with TTL."""
    _cache[key] = (value, time.monotonic() + ttl)


def invalidate(key: str | None = None, prefix: bool = False) -> None:
    """Invalidate cache. key=None clears all. prefix=True treats key as prefix."""
    if key is None:
        _log.debug("Cache: invalidate all")
        _cache.clear()
        return
    if prefix:
        to_remove = [k for k in _cache if k.startswith(key)]
        for k in to_remove:
            del _cache[k]
        _log.debug("Cache: invalidate prefix %s (%d keys)", key, len(to_remove))
    elif key in _cache:
        del _cache[key]
        _log.debug("Cache: invalidate %s", key)
