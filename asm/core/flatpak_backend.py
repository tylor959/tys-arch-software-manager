"""Flatpak backend — manages Flatpak apps, Flathub browsing, and auto-setup.

Wraps the flatpak CLI and optionally queries the Flathub API for richer metadata.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field

FLATHUB_API = "https://flathub.org/api/v2"
REQUEST_TIMEOUT = 15


@dataclass
class FlatpakApp:
    """Flatpak application info."""
    app_id: str = ""
    name: str = ""
    description: str = ""
    version: str = ""
    branch: str = ""
    origin: str = ""
    installed_size: str = ""
    is_installed: bool = False
    icon_url: str = ""


def is_available() -> bool:
    """Check if flatpak is installed."""
    return shutil.which("flatpak") is not None


def has_flathub() -> bool:
    """Check if the Flathub remote is configured."""
    if not is_available():
        return False
    try:
        result = subprocess.run(
            ["flatpak", "remotes"], capture_output=True, text=True, timeout=10,
        )
        return "flathub" in result.stdout.lower()
    except Exception:
        return False


def setup_flathub_command() -> list[str]:
    """Return the command to add Flathub remote."""
    return [
        "flatpak", "remote-add", "--if-not-exists",
        "flathub", "https://dl.flathub.org/repo/flathub.flatpakrepo",
    ]


def list_installed() -> list[FlatpakApp]:
    """List installed Flatpak apps."""
    if not is_available():
        return []
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application,name,version,branch,origin,size"],
            capture_output=True, text=True, timeout=15,
        )
        apps = []
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                apps.append(FlatpakApp(
                    app_id=parts[0].strip(),
                    name=parts[1].strip() if len(parts) > 1 else parts[0],
                    version=parts[2].strip() if len(parts) > 2 else "",
                    branch=parts[3].strip() if len(parts) > 3 else "",
                    origin=parts[4].strip() if len(parts) > 4 else "",
                    installed_size=parts[5].strip() if len(parts) > 5 else "",
                    is_installed=True,
                ))
        return apps
    except Exception:
        return []


def search_flathub(query: str) -> list[FlatpakApp]:
    """Search Flathub via the flatpak CLI."""
    if not is_available():
        return []
    try:
        result = subprocess.run(
            ["flatpak", "search", query, "--columns=application,name,description,version,branch,remotes"],
            capture_output=True, text=True, timeout=15,
        )
        apps = []
        installed = {a.app_id for a in list_installed()}
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2:
                app_id = parts[0].strip()
                apps.append(FlatpakApp(
                    app_id=app_id,
                    name=parts[1].strip() if len(parts) > 1 else app_id,
                    description=parts[2].strip() if len(parts) > 2 else "",
                    version=parts[3].strip() if len(parts) > 3 else "",
                    branch=parts[4].strip() if len(parts) > 4 else "",
                    origin=parts[5].strip() if len(parts) > 5 else "",
                    is_installed=app_id in installed,
                ))
        return apps
    except Exception:
        return []


def search_flathub_api(query: str) -> list[FlatpakApp]:
    """Search Flathub via REST API for richer metadata including icons."""
    try:
        payload = json.dumps({"query": query, "filters": []}).encode()
        req = urllib.request.Request(
            f"{FLATHUB_API}/search",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "TysASM/1.0"},
            method="POST",
        )
        resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
        data = json.loads(resp.read().decode())

        installed = {a.app_id for a in list_installed()} if is_available() else set()
        apps = []
        for item in data.get("hits", []):
            app_id = item.get("app_id", "")
            icon = item.get("icon", "")
            if icon and not icon.startswith("http"):
                icon = f"https://dl.flathub.org/repo/appstream/x86_64/icons/128x128/{icon}"
            apps.append(FlatpakApp(
                app_id=app_id,
                name=item.get("name", app_id),
                description=item.get("summary", ""),
                is_installed=app_id in installed,
                icon_url=icon,
            ))
        return apps
    except Exception:
        return search_flathub(query)


def install_command(app_id: str) -> list[str]:
    """Return command to install a Flatpak app."""
    return ["flatpak", "install", "-y", "flathub", app_id]


def remove_command(app_id: str) -> list[str]:
    """Return command to remove a Flatpak app."""
    return ["flatpak", "uninstall", "-y", app_id]


def update_command() -> list[str]:
    """Return command to update all Flatpak apps."""
    return ["flatpak", "update", "-y"]
