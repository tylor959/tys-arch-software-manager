"""Unified package manager facade — routes operations to the correct backend."""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from asm.core import pacman_backend, paru_backend, flatpak_backend


class Backend(Enum):
    PACMAN = "pacman"
    AUR = "aur"
    FLATPAK = "flatpak"


def detect_backend(pkg_name: str) -> Backend:
    """Try to detect which backend a package belongs to."""
    if pacman_backend.is_installed(pkg_name):
        return Backend.PACMAN

    from asm.core.aur_client import info as aur_info
    aur_results = aur_info([pkg_name])
    if aur_results:
        return Backend.AUR

    if flatpak_backend.is_available():
        installed = flatpak_backend.list_installed()
        if any(a.app_id == pkg_name or a.name == pkg_name for a in installed):
            return Backend.FLATPAK

    return Backend.PACMAN


def install_command(pkg_name: str, backend: Backend) -> list[str]:
    """Return the install command for the given backend."""
    if backend == Backend.PACMAN:
        return pacman_backend.install_command([pkg_name])
    elif backend == Backend.AUR:
        if paru_backend.is_available():
            return paru_backend.install_command([pkg_name])
        return ["echo", "No AUR helper available"]
    elif backend == Backend.FLATPAK:
        return flatpak_backend.install_command(pkg_name)
    return []


def remove_command(pkg_name: str, backend: Backend) -> list[str]:
    """Return the remove command for the given backend."""
    if backend == Backend.PACMAN:
        return pacman_backend.remove_command([pkg_name])
    elif backend == Backend.AUR:
        if paru_backend.is_available():
            return paru_backend.remove_command([pkg_name])
        return pacman_backend.remove_command([pkg_name])
    elif backend == Backend.FLATPAK:
        return flatpak_backend.remove_command(pkg_name)
    return []


def needs_privilege(backend: Backend, action: str = "install") -> bool:
    """Check if a backend action needs privilege escalation."""
    if backend == Backend.PACMAN:
        return True
    if backend == Backend.AUR:
        return False  # paru handles its own privilege
    if backend == Backend.FLATPAK:
        return False  # flatpak --user doesn't need root
    return True
