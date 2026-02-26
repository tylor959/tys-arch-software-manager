"""Pacman backend — wraps pacman commands for querying, installing, and removing packages."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence


@dataclass
class PackageInfo:
    """Structured info about an installed or available package."""
    name: str = ""
    version: str = ""
    description: str = ""
    installed_size: str = ""
    installed_size_bytes: int = 0
    download_size: str = ""
    repository: str = ""
    url: str = ""
    depends: list[str] = field(default_factory=list)
    optional_deps: list[str] = field(default_factory=list)
    install_date: str = ""
    groups: list[str] = field(default_factory=list)
    provides: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    is_installed: bool = False
    desktop_files: list[str] = field(default_factory=list)


def _run(cmd: Sequence[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return ""


def _parse_size_to_bytes(size_str: str) -> int:
    """Convert a size string like '272.34 MiB' to bytes."""
    match = re.match(r"([\d.]+)\s*(B|KiB|MiB|GiB|TiB)", size_str.strip())
    if not match:
        return 0
    val = float(match.group(1))
    unit = match.group(2)
    multiplier = {"B": 1, "KiB": 1024, "MiB": 1024**2, "GiB": 1024**3, "TiB": 1024**4}
    return int(val * multiplier.get(unit, 1))


def list_installed() -> list[PackageInfo]:
    """List all installed packages (name + version)."""
    output = _run(["pacman", "-Q"])
    packages = []
    for line in output.strip().splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) >= 2:
            packages.append(PackageInfo(name=parts[0], version=parts[1], is_installed=True))
        elif parts:
            packages.append(PackageInfo(name=parts[0], is_installed=True))
    return packages


def list_installed_detailed() -> dict[str, PackageInfo]:
    """Get detailed info for ALL installed packages in a single pacman call.

    Returns a dict mapping package name -> PackageInfo. This is dramatically
    faster than calling get_package_info() per package (1 subprocess vs 1400+).
    """
    output = _run(["pacman", "-Qi"], timeout=60)
    if not output.strip():
        return {}

    result: dict[str, PackageInfo] = {}
    # pacman -Qi separates packages with blank lines
    blocks = re.split(r"\n\n+", output.strip())
    for block in blocks:
        if not block.strip():
            continue
        info = _parse_info_block(block, is_installed=True)
        if info.name:
            result[info.name] = info
    return result


def get_package_info(name: str, installed: bool = True) -> PackageInfo | None:
    """Get detailed info for a single package."""
    flag = "-Qi" if installed else "-Si"
    output = _run(["pacman", flag, name])
    if not output.strip():
        return None
    return _parse_info_block(output, is_installed=installed)


def _parse_info_block(output: str, is_installed: bool = True) -> PackageInfo:
    info = PackageInfo(is_installed=is_installed)
    field_map = {
        "Name": "name",
        "Version": "version",
        "Description": "description",
        "Installed Size": "installed_size",
        "Download Size": "download_size",
        "Repository": "repository",
        "URL": "url",
        "Install Date": "install_date",
    }
    current_key = ""
    for line in output.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            current_key = key

            if key in field_map:
                setattr(info, field_map[key], value)
            elif key == "Depends On" and value != "None":
                info.depends = value.split()
            elif key == "Optional Deps":
                if value and value != "None":
                    info.optional_deps.append(value)
            elif key == "Groups" and value != "None":
                info.groups = value.split()
            elif key == "Provides" and value != "None":
                info.provides = value.split()
        elif current_key == "Optional Deps" and line.startswith(" "):
            info.optional_deps.append(line.strip())

    if info.installed_size:
        info.installed_size_bytes = _parse_size_to_bytes(info.installed_size)

    return info


def get_package_files(name: str) -> list[str]:
    """Get list of files owned by a package."""
    output = _run(["pacman", "-Ql", name])
    files = []
    for line in output.strip().splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            files.append(parts[1])
    return files


def search_repos(query: str) -> list[PackageInfo]:
    """Search official repos for packages matching query."""
    output = _run(["pacman", "-Ss", query], timeout=15)
    packages = []
    lines = output.strip().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line and not line.startswith(" "):
            match = re.match(r"^(\S+)/(\S+)\s+(\S+)(?:\s+(.*))?$", line)
            if match:
                repo, name, version = match.group(1), match.group(2), match.group(3)
                extra = match.group(4) or ""
                desc = ""
                if i + 1 < len(lines) and lines[i + 1].startswith("    "):
                    desc = lines[i + 1].strip()
                    i += 1
                pkg = PackageInfo(
                    name=name, version=version, description=desc,
                    repository=repo, is_installed="[installed]" in extra,
                )
                packages.append(pkg)
        i += 1
    return packages


def get_groups() -> list[str]:
    """Return list of all pacman package groups."""
    output = _run(["pacman", "-Sg"])
    groups = sorted(set(line.split()[0] for line in output.strip().splitlines() if line.strip()))
    return groups


def get_group_packages(group: str) -> list[str]:
    """Return package names in a given group."""
    output = _run(["pacman", "-Sgq", group])
    return [line.strip() for line in output.strip().splitlines() if line.strip()]


def install_command(names: Sequence[str]) -> list[str]:
    """Return the command list for installing packages from repos."""
    return ["pacman", "-S", "--noconfirm"] + list(names)


def remove_command(names: Sequence[str], recursive: bool = True) -> list[str]:
    """Return the command list for removing packages."""
    flag = "-Rns" if recursive else "-R"
    return ["pacman", flag, "--noconfirm"] + list(names)


def is_installed(name: str) -> bool:
    """Check if a package is installed."""
    result = subprocess.run(["pacman", "-Q", name], capture_output=True)
    return result.returncode == 0
