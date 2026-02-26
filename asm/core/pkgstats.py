"""Fetch package popularity from pkgstats.archlinux.de.

The pkgstats service collects anonymous statistics from users who
opt-in via the `pkgstats` package.  Popularity is reported as the
percentage of participating systems that have a given package installed.

Results are cached locally with a 24-hour TTL to avoid hitting the API
on every search.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Sequence

import requests

from asm.core.config import CACHE_DIR

_CACHE_FILE = CACHE_DIR / "pkgstats.json"
_API_URL = "https://pkgstats.archlinux.de/api/packages"
_TTL_SECONDS = 86400  # 24 hours
_MAX_WORKERS = 12
_TIMEOUT = 4  # seconds per request


def _load_cache() -> dict:
    try:
        if _CACHE_FILE.exists():
            return json.loads(_CACHE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_FILE.write_text(json.dumps(cache))
    except OSError:
        pass


def _fetch_one(name: str) -> tuple[str, float | None]:
    """Fetch popularity for a single package.  Returns (name, popularity)."""
    try:
        resp = requests.get(f"{_API_URL}/{name}", timeout=_TIMEOUT)
        if resp.status_code == 200:
            data = resp.json()
            return name, float(data.get("popularity", 0))
    except Exception:
        pass
    return name, None


def get_popularity_batch(names: Sequence[str]) -> dict[str, float]:
    """Fetch popularity for multiple packages in parallel.

    Returns a dict of {package_name: popularity_pct}.  Packages with no
    data or that fail to fetch are omitted from the result.  Results are
    cached for 24 hours.
    """
    cache = _load_cache()
    now = time.time()
    result: dict[str, float] = {}
    to_fetch: list[str] = []

    for name in names:
        entry = cache.get(name)
        if entry and now - entry.get("ts", 0) < _TTL_SECONDS:
            pop = entry.get("pop")
            if pop is not None:
                result[name] = pop
        else:
            to_fetch.append(name)

    if to_fetch:
        with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as pool:
            futures = {pool.submit(_fetch_one, n): n for n in to_fetch}
            for future in as_completed(futures):
                name, pop = future.result()
                cache[name] = {"pop": pop, "ts": now}
                if pop is not None:
                    result[name] = pop

        _save_cache(cache)

    return result
