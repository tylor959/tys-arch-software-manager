""".desktop file parser — extracts app metadata (name, icon, exec, categories)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

APPLICATIONS_DIRS = [
    Path("/usr/share/applications"),
    Path("/usr/local/share/applications"),
    Path.home() / ".local" / "share" / "applications",
]


@dataclass
class DesktopEntry:
    """Parsed fields from a .desktop file."""
    file_path: str = ""
    name: str = ""
    generic_name: str = ""
    comment: str = ""
    icon: str = ""
    exec_cmd: str = ""
    categories: list[str] = field(default_factory=list)
    no_display: bool = False
    terminal: bool = False
    type: str = "Application"


def parse_desktop_file(path: str | Path) -> DesktopEntry | None:
    """Parse a single .desktop file and return a DesktopEntry, or None on failure."""
    entry = DesktopEntry(file_path=str(path))
    in_desktop_entry = False
    try:
        with open(path, "r", errors="replace") as f:
            for raw_line in f:
                line = raw_line.strip()
                if line == "[Desktop Entry]":
                    in_desktop_entry = True
                    continue
                if line.startswith("[") and line.endswith("]"):
                    if in_desktop_entry:
                        break
                    continue
                if not in_desktop_entry or "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip()

                if key == "Name" or (key.startswith("Name[") and not entry.name):
                    if key == "Name":
                        entry.name = value
                elif key == "GenericName":
                    entry.generic_name = value
                elif key == "Comment":
                    entry.comment = value
                elif key == "Icon":
                    entry.icon = value
                elif key == "Exec":
                    entry.exec_cmd = value
                elif key == "Categories":
                    entry.categories = [c for c in value.split(";") if c]
                elif key == "NoDisplay":
                    entry.no_display = value.lower() == "true"
                elif key == "Terminal":
                    entry.terminal = value.lower() == "true"
                elif key == "Type":
                    entry.type = value
    except OSError:
        return None

    if not entry.name:
        return None
    return entry


def get_all_desktop_entries() -> dict[str, DesktopEntry]:
    """Return a dict mapping .desktop filename stem -> DesktopEntry for all visible apps."""
    entries: dict[str, DesktopEntry] = {}
    for d in APPLICATIONS_DIRS:
        if not d.is_dir():
            continue
        for f in d.iterdir():
            if not f.suffix == ".desktop":
                continue
            entry = parse_desktop_file(f)
            if entry and entry.type == "Application" and not entry.no_display:
                entries[f.stem] = entry
    return entries


def find_desktop_for_package(pkg_name: str, entries: dict[str, DesktopEntry] | None = None) -> DesktopEntry | None:
    """Try to find a .desktop entry matching a package name."""
    if entries is None:
        entries = get_all_desktop_entries()

    if pkg_name in entries:
        return entries[pkg_name]

    pkg_lower = pkg_name.lower()
    for stem, entry in entries.items():
        if stem.lower() == pkg_lower:
            return entry

    for stem, entry in entries.items():
        if pkg_lower in stem.lower() or pkg_lower in entry.name.lower():
            return entry

    return None
