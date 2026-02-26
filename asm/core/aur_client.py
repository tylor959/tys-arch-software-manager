"""AUR RPC v5 API client — searches and retrieves package info from the AUR.

Falls back to paru when available for actual installations.
"""

from __future__ import annotations

import json
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Literal

AUR_RPC_URL = "https://aur.archlinux.org/rpc/"
AUR_PACKAGE_URL = "https://aur.archlinux.org/packages/"
REQUEST_TIMEOUT = 15


@dataclass
class AURPackage:
    """Structured AUR package info."""
    name: str = ""
    description: str = ""
    version: str = ""
    votes: int = 0
    popularity: float = 0.0
    maintainer: str = ""
    url: str = ""
    aur_url: str = ""
    out_of_date: bool = False
    first_submitted: int = 0
    last_modified: int = 0
    package_base: str = ""


def search(query: str, by: str = "name-desc") -> list[AURPackage]:
    """Search AUR packages by query string.

    Args:
        query: Search term
        by: Search field — "name", "name-desc", or "maintainer"
    """
    params = urllib.parse.urlencode({"v": 5, "type": "search", "by": by, "arg": query})
    url = f"{AUR_RPC_URL}?{params}"
    data = _fetch(url)
    if data is None:
        return []
    return [_parse_result(r) for r in data.get("results", [])]


def info(names: list[str]) -> list[AURPackage]:
    """Get detailed info for specific AUR packages."""
    if not names:
        return []
    params = [("v", "5"), ("type", "info")]
    for n in names:
        params.append(("arg[]", n))
    url = f"{AUR_RPC_URL}?{urllib.parse.urlencode(params)}"
    data = _fetch(url)
    if data is None:
        return []
    return [_parse_result(r) for r in data.get("results", [])]


def _fetch(url: str) -> dict | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "TysASM/1.0"})
        resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
        return json.loads(resp.read().decode())
    except Exception:
        return None


def _parse_result(r: dict) -> AURPackage:
    return AURPackage(
        name=r.get("Name", ""),
        description=r.get("Description", "") or "",
        version=r.get("Version", ""),
        votes=r.get("NumVotes", 0),
        popularity=r.get("Popularity", 0.0),
        maintainer=r.get("Maintainer", "") or "",
        url=r.get("URL", "") or "",
        aur_url=f"{AUR_PACKAGE_URL}{r.get('Name', '')}",
        out_of_date=r.get("OutOfDate") is not None,
        first_submitted=r.get("FirstSubmitted", 0),
        last_modified=r.get("LastModified", 0),
        package_base=r.get("PackageBase", ""),
    )
