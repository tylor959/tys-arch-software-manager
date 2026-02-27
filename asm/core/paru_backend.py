"""Paru backend — wraps the paru AUR helper for installing/searching AUR packages.

Falls back gracefully if paru is not installed.
Supports yay as fallback when paru is unavailable.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Sequence

from asm.core.logger import get_logger

_log = get_logger("paru_backend")


def is_available() -> bool:
    """Check if paru is installed."""
    return shutil.which("paru") is not None


def get_aur_helper() -> str | None:
    """Return the best available AUR helper (paru, then yay), or None."""
    if shutil.which("paru"):
        _log.debug("AUR helper: paru")
        return "paru"
    if shutil.which("yay"):
        _log.debug("AUR helper: yay")
        return "yay"
    _log.info("AUR helper: none available (paru/yay not found)")
    return None


def install_command(names: Sequence[str]) -> list[str]:
    """Return the paru command to install AUR packages (non-interactive)."""
    return ["paru", "-S", "--noconfirm", "--skipreview"] + list(names)


def install_command_for_helper(helper: str, names: Sequence[str]) -> list[str]:
    """Return install command for the given AUR helper (paru or yay)."""
    if helper == "yay":
        return ["yay", "-S", "--noconfirm"] + list(names)
    return ["paru", "-S", "--noconfirm", "--skipreview"] + list(names)


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


def remove_command(names: Sequence[str]) -> list[str]:
    """Return the paru command to remove packages."""
    return ["paru", "-Rns", "--noconfirm"] + list(names)


def build_command(pkgbase: str) -> list[str]:
    """Return a paru command to build a specific AUR package."""
    return ["paru", "-S", "--noconfirm", "--skipreview", pkgbase]
