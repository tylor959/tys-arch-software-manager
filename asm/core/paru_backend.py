"""Paru backend — wraps the paru AUR helper for installing/searching AUR packages.

Falls back gracefully if paru is not installed.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Sequence


def is_available() -> bool:
    """Check if paru is installed."""
    return shutil.which("paru") is not None


def search(query: str) -> str:
    """Search AUR via paru. Returns raw output."""
    if not is_available():
        return ""
    try:
        result = subprocess.run(
            ["paru", "-Ss", "--aur", query],
            capture_output=True, text=True, timeout=30,
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def install_command(names: Sequence[str]) -> list[str]:
    """Return the paru command to install AUR packages (non-interactive)."""
    return ["paru", "-S", "--noconfirm", "--skipreview"] + list(names)


def remove_command(names: Sequence[str]) -> list[str]:
    """Return the paru command to remove packages."""
    return ["paru", "-Rns", "--noconfirm"] + list(names)


def build_command(pkgbase: str) -> list[str]:
    """Return a paru command to build a specific AUR package."""
    return ["paru", "-S", "--noconfirm", "--skipreview", pkgbase]
