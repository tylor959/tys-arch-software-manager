"""Self-healing diagnostics engine — pre/post install checks and one-click fixes.

Checks: disk space, keyring health, orphaned packages, broken symlinks,
        mirror status, package cache size.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


@dataclass
class DiagnosticResult:
    name: str
    status: str   # "ok", "warning", "error"
    message: str
    fix_label: str = ""
    fix_cmd: list[str] | None = None


def run_all_checks() -> list[DiagnosticResult]:
    """Run all diagnostic checks and return results."""
    checks: list[Callable[[], DiagnosticResult]] = [
        check_disk_space,
        check_keyring,
        check_orphans,
        check_pacman_cache,
        check_failed_services,
        check_broken_symlinks,
        check_pacman_lock,
    ]
    return [c() for c in checks]


def check_disk_space() -> DiagnosticResult:
    """Check available disk space on root partition."""
    try:
        total, used, free = shutil.disk_usage("/")
        free_gb = free / (1024**3)
        pct_used = (used / total) * 100
        if free_gb < 1:
            return DiagnosticResult(
                "Disk Space", "error",
                f"Critical: Only {free_gb:.1f} GB free ({pct_used:.0f}% used)",
                fix_label="Clean package cache",
                fix_cmd=["pacman", "-Scc", "--noconfirm"],
            )
        elif free_gb < 5:
            return DiagnosticResult(
                "Disk Space", "warning",
                f"Low disk space: {free_gb:.1f} GB free ({pct_used:.0f}% used)",
                fix_label="Clean package cache",
                fix_cmd=["pacman", "-Sc", "--noconfirm"],
            )
        return DiagnosticResult("Disk Space", "ok", f"{free_gb:.1f} GB free ({pct_used:.0f}% used)")
    except Exception as e:
        return DiagnosticResult("Disk Space", "error", str(e))


def check_keyring() -> DiagnosticResult:
    """Verify pacman keyring health."""
    try:
        result = subprocess.run(
            ["pacman-key", "--verify", "/etc/pacman.d/gnupg/pubring.gpg"],
            capture_output=True, text=True, timeout=10,
        )
        # If the keyring file doesn't exist or is corrupted
        if result.returncode != 0:
            return DiagnosticResult(
                "Pacman Keyring", "warning",
                "Keyring may need refresh",
                fix_label="Refresh keyring",
                fix_cmd=["pacman-key", "--init"],
            )
        return DiagnosticResult("Pacman Keyring", "ok", "Keyring is healthy")
    except subprocess.TimeoutExpired:
        return DiagnosticResult("Pacman Keyring", "warning", "Keyring check timed out")
    except Exception:
        return DiagnosticResult(
            "Pacman Keyring", "warning",
            "Could not verify keyring",
            fix_label="Re-initialize keyring",
            fix_cmd=["pacman-key", "--init"],
        )


def check_orphans() -> DiagnosticResult:
    """Check for orphaned packages (installed as deps but no longer needed)."""
    try:
        result = subprocess.run(
            ["pacman", "-Qdtq"], capture_output=True, text=True, timeout=10,
        )
        orphans = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if orphans:
            return DiagnosticResult(
                "Orphaned Packages", "warning",
                f"{len(orphans)} orphaned packages found: {', '.join(orphans[:5])}{'...' if len(orphans) > 5 else ''}",
                fix_label="Remove orphans",
                fix_cmd=["pacman", "-Rns", "--noconfirm"] + orphans,
            )
        return DiagnosticResult("Orphaned Packages", "ok", "No orphaned packages")
    except Exception as e:
        return DiagnosticResult("Orphaned Packages", "error", str(e))


def check_pacman_cache() -> DiagnosticResult:
    """Check package cache size."""
    cache_dir = Path("/var/cache/pacman/pkg")
    try:
        total = sum(f.stat().st_size for f in cache_dir.iterdir() if f.is_file())
        gb = total / (1024**3)
        if gb > 5:
            return DiagnosticResult(
                "Package Cache", "warning",
                f"Cache is {gb:.1f} GB",
                fix_label="Clean old versions",
                fix_cmd=["paccache", "-r"],
            )
        return DiagnosticResult("Package Cache", "ok", f"Cache is {gb:.1f} GB")
    except Exception as e:
        return DiagnosticResult("Package Cache", "error", str(e))


def check_failed_services() -> DiagnosticResult:
    """Check for failed systemd services."""
    try:
        result = subprocess.run(
            ["systemctl", "--failed", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=10,
        )
        lines = [l for l in result.stdout.strip().splitlines() if l.strip()]
        if lines:
            return DiagnosticResult(
                "System Services", "warning",
                f"{len(lines)} failed service(s)",
            )
        return DiagnosticResult("System Services", "ok", "All services running")
    except Exception:
        return DiagnosticResult("System Services", "ok", "Could not check services")


def check_broken_symlinks() -> DiagnosticResult:
    """Quick check for broken symlinks in common directories."""
    broken = []
    for check_dir in ["/usr/bin", "/usr/lib"]:
        try:
            for entry in os.scandir(check_dir):
                if entry.is_symlink() and not os.path.exists(entry.path):
                    broken.append(entry.path)
                    if len(broken) >= 10:
                        break
        except OSError:
            continue
        if len(broken) >= 10:
            break

    if broken:
        return DiagnosticResult(
            "Broken Symlinks", "warning",
            f"{len(broken)} broken symlink(s) found in system dirs",
        )
    return DiagnosticResult("Broken Symlinks", "ok", "No broken symlinks detected")


def check_pacman_lock() -> DiagnosticResult:
    """Check if pacman lock file exists (indicates another process running)."""
    lock = Path("/var/lib/pacman/db.lck")
    if lock.exists():
        return DiagnosticResult(
            "Pacman Lock", "error",
            "Lock file exists — another package operation may be running",
            fix_label="Remove lock file",
            fix_cmd=["rm", "-f", "/var/lib/pacman/db.lck"],
        )
    return DiagnosticResult("Pacman Lock", "ok", "No lock file — pacman is ready")


# ── Pre/Post install checks ──

def pre_install_check(pkg_names: list[str]) -> list[DiagnosticResult]:
    """Run checks before installing packages."""
    results = []
    results.append(check_disk_space())
    results.append(check_pacman_lock())

    # Check for conflicts
    for name in pkg_names:
        result = subprocess.run(
            ["pacman", "-Si", name], capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            results.append(DiagnosticResult(
                f"Package '{name}'", "warning",
                f"Package info not found — may not exist in repos",
            ))
    return results


def post_install_check(pkg_names: list[str]) -> list[DiagnosticResult]:
    """Verify installation was successful."""
    from asm.core.pacman_backend import is_installed
    results = []
    for name in pkg_names:
        if is_installed(name):
            results.append(DiagnosticResult(name, "ok", "Successfully installed"))
        else:
            results.append(DiagnosticResult(
                name, "error",
                "Package not found after installation — may have failed",
            ))
    return results
