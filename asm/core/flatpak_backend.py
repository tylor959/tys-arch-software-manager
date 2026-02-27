"""Flatpak backend — manages Flatpak apps, Flathub browsing, and auto-setup.

Wraps the flatpak CLI and optionally queries the Flathub API for richer metadata.
"""

from __future__ import annotations

import configparser
import json
import os
import shutil
import subprocess
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from asm.core.cache import get, set_, invalidate, CACHE_TTL_INSTALLED, CACHE_TTL_SEARCH

FLATHUB_API = "https://flathub.org/api/v2"
INSTALLATIONS_DIR = Path("/etc/flatpak/installations.d")
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
    """List installed Flatpak apps. Cached 60s."""
    if not is_available():
        return []
    cached_result = get("flatpak_installed", CACHE_TTL_INSTALLED)
    if cached_result is not None:
        return cached_result
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
        set_("flatpak_installed", apps, CACHE_TTL_INSTALLED)
        return apps
    except Exception:
        return []


def invalidate_flatpak_cache() -> None:
    """Call after install/remove to refresh app list."""
    invalidate("flatpak_installed")
    invalidate("flatpak_search", prefix=True)


def search_flathub(query: str) -> list[FlatpakApp]:
    """Search Flathub via the flatpak CLI. Cached 5 min."""
    if not is_available():
        return []
    cache_key = f"flatpak_search_cli:{query}"
    cached_result = get(cache_key, CACHE_TTL_SEARCH)
    if cached_result is not None:
        return cached_result
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
        set_(cache_key, apps, CACHE_TTL_SEARCH)
        return apps
    except Exception:
        return []


def search_flathub_api(query: str) -> list[FlatpakApp]:
    """Search Flathub via REST API for richer metadata including icons. Cached 5 min."""
    cache_key = f"flatpak_search_api:{query}"
    cached_result = get(cache_key, CACHE_TTL_SEARCH)
    if cached_result is not None:
        return cached_result
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
        set_(cache_key, apps, CACHE_TTL_SEARCH)
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


# ── Custom installations (move to disk) ──

@dataclass
class FlatpakInstallation:
    """A Flatpak installation (default or custom)."""
    id: str
    path: str
    display_name: str


def list_installations() -> list[FlatpakInstallation]:
    """List available Flatpak installations (default + custom from /etc/flatpak/installations.d)."""
    installations = [
        FlatpakInstallation(id="system", path="/var/lib/flatpak", display_name="System (default)"),
    ]
    if not INSTALLATIONS_DIR.is_dir():
        return installations
    for conf_file in INSTALLATIONS_DIR.glob("*.conf"):
        try:
            parser = configparser.ConfigParser()
            parser.read(conf_file)
            for section in parser.sections():
                if section.startswith("Installation "):
                    id_val = parser.get(section, "Id", fallback="").strip('"')
                    if not id_val and '"' in section:
                        id_val = section.split('"', 2)[1]
                    path_val = parser.get(section, "Path", fallback="").strip('"')
                    display_val = parser.get(section, "DisplayName", fallback=id_val).strip('"')
                    if id_val and path_val and os.path.isdir(path_val):
                        installations.append(
                            FlatpakInstallation(id=id_val, path=path_val, display_name=display_val or id_val)
                        )
        except (configparser.Error, OSError):
            continue
    return installations


def get_installation_for_app(app_id: str) -> str | None:
    """Return the installation id where the app is installed, or None."""
    if not is_available():
        return None
    try:
        result = subprocess.run(
            ["flatpak", "info", "--show-location", app_id],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            return None
        loc = result.stdout.strip()
        if "/var/lib/flatpak" in loc:
            return "system"
        for inst in list_installations():
            if inst.id != "system" and inst.path in loc:
                return inst.id
        return "system"
    except Exception:
        return None


def uninstall_command(app_id: str, installation: str | None = None) -> list[str]:
    """Return command to uninstall. installation=None uses default."""
    cmd = ["flatpak", "uninstall", "-y", app_id]
    if installation and installation != "system":
        cmd = ["flatpak", "--installation", installation, "uninstall", "-y", app_id]
    return cmd


def install_to_installation_command(app_id: str, installation_id: str) -> list[str]:
    """Return command to install app to a specific installation."""
    if installation_id == "system":
        return ["flatpak", "install", "-y", "flathub", app_id]
    return ["flatpak", "--installation", installation_id, "install", "-y", "flathub", app_id]
