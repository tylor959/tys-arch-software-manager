"""Snap backend — search, list, install, remove Snap packages.

Uses snap CLI (snap find, snap list, snap install, snap remove).
Snap is available on Arch via AUR (snapd).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass

SNAP_API_V1_URL = "https://api.snapcraft.io/api/v1/snaps/search"
REQUEST_TIMEOUT = 15


@dataclass
class SnapApp:
    """Snap application info."""
    name: str = ""
    summary: str = ""
    version: str = ""
    publisher: str = ""
    is_installed: bool = False
    installed_version: str = ""


def is_available() -> bool:
    """Check if snap CLI is installed."""
    return shutil.which("snap") is not None


def list_installed() -> list[SnapApp]:
    """List installed Snap packages (excluding base/core)."""
    if not is_available():
        return []
    try:
        result = subprocess.run(
            ["snap", "list"],
            capture_output=True, text=True, timeout=15,
        )
        apps = []
        for line in result.stdout.strip().splitlines()[1:]:  # skip header
            parts = line.split(maxsplit=5)
            if len(parts) >= 3:
                name = parts[0]
                if name in ("core", "core18", "core20", "core22", "snapd"):
                    continue
                apps.append(SnapApp(
                    name=name,
                    version=parts[1] if len(parts) > 1 else "",
                    summary="",
                    is_installed=True,
                    installed_version=parts[1] if len(parts) > 1 else "",
                ))
        return apps
    except Exception:
        return []


def _search_cli(query: str) -> list[SnapApp]:
    """Search via snap find CLI."""
    try:
        result = subprocess.run(
            ["snap", "find", query],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return []
        apps = []
        lines = result.stdout.strip().splitlines()
        if len(lines) < 2:
            return apps
        for line in lines[1:]:  # skip header
            parts = line.split(maxsplit=4)
            if len(parts) >= 3:
                apps.append(SnapApp(
                    name=parts[0],
                    version=parts[1],
                    summary=parts[4] if len(parts) > 4 else "",
                    publisher=parts[2] if len(parts) > 2 else "",
                ))
        return apps
    except Exception:
        return []


def _search_api(query: str) -> list[SnapApp]:
    """Search via Snap Store API v1."""
    try:
        url = f"{SNAP_API_V1_URL}?q={urllib.request.quote(query)}&page_size=50"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "TysASM/1.0",
                "Snap-Device-Series": "16",
            },
        )
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
        installed = {a.name: a.installed_version for a in list_installed()}
        packages = data.get("_embedded", {}).get("clickindex:package", [])
        apps = []
        for item in packages:
            name = item.get("package_name", "").strip()
            if not name:
                continue
            apps.append(SnapApp(
                name=name,
                summary=item.get("summary", ""),
                version=item.get("version", ""),
                publisher=item.get("publisher", {}).get("display-name", ""),
                is_installed=name in installed,
                installed_version=installed.get(name, ""),
            ))
        return apps
    except Exception:
        return []


def search(query: str) -> list[SnapApp]:
    """Search Snap packages. Tries API first, falls back to CLI."""
    if not is_available():
        return []
    if not query.strip():
        return []
    results = _search_api(query)
    if not results:
        results = _search_cli(query)
    # Mark installed
    installed = {a.name: a for a in list_installed()}
    for app in results:
        if app.name in installed:
            app.is_installed = True
            app.installed_version = installed[app.name].installed_version
    return results


def install_command(name: str) -> list[str]:
    """Return command to install a Snap."""
    return ["snap", "install", name]


def remove_command(name: str) -> list[str]:
    """Return command to remove a Snap."""
    return ["snap", "remove", name]


def install_snapd_command() -> list[str] | None:
    """Return command to install snapd (via paru or yay from AUR), or None if no AUR helper."""
    from asm.core.paru_backend import get_aur_helper, install_command_for_helper
    helper = get_aur_helper()
    if helper:
        return install_command_for_helper(helper, ["snapd"])
    return None
