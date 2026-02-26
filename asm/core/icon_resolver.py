"""Multi-source icon resolution chain with local caching.

Resolution order:
  1. User-custom icon (~/.config/tys-asm/custom-icons/{name}.png)
  2. .desktop Icon= field resolved against system icon themes
  3. System icon theme search (breeze, Adwaita, hicolor, Papirus)
  4. Cache hit (~/.cache/tys-asm/icons/)
  5. Generic fallback (bundled)
"""

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache

from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QApplication

from asm.core.config import CUSTOM_ICONS_DIR, ICON_CACHE_DIR

ICON_THEME_DIRS = [
    Path("/usr/share/icons"),
    Path.home() / ".local" / "share" / "icons",
    Path.home() / ".icons",
]

THEME_SEARCH_ORDER = ["hicolor", "breeze", "breeze-dark", "Adwaita", "Papirus", "Papirus-Dark"]

ICON_EXTENSIONS = [".svg", ".png", ".xpm"]
ICON_SIZES = ["scalable", "256x256", "128x128", "96x96", "64x64", "48x48", "32x32", "24x24", "22x22", "16x16"]
ICON_CATEGORIES = ["apps", "applications", "mimetypes", "categories", "places"]

_FALLBACK_PIXMAP: QPixmap | None = None


def _get_fallback_pixmap() -> QPixmap:
    global _FALLBACK_PIXMAP
    if _FALLBACK_PIXMAP is None:
        _FALLBACK_PIXMAP = QPixmap(48, 48)
        _FALLBACK_PIXMAP.fill()
    return _FALLBACK_PIXMAP


def resolve_icon(name: str, desktop_icon_field: str = "") -> QIcon:
    """Resolve an icon by name through the full resolution chain."""
    icon_name = desktop_icon_field or name

    if not icon_name:
        return QIcon(_get_fallback_pixmap())

    # 1) User-custom icon
    icon = _check_custom(name)
    if icon and not icon.isNull():
        return icon

    # 2) If desktop_icon_field is an absolute path
    if icon_name.startswith("/") and os.path.isfile(icon_name):
        return QIcon(icon_name)

    # 3) Qt theme lookup (fast, uses system theme)
    icon = QIcon.fromTheme(icon_name)
    if icon and not icon.isNull():
        return icon

    # 4) Manual theme directory search
    icon = _search_themes(icon_name)
    if icon and not icon.isNull():
        _cache_icon(name, icon)
        return icon

    # 5) Cache check
    icon = _check_cache(name)
    if icon and not icon.isNull():
        return icon

    # 6) Fallback
    return QIcon.fromTheme("application-x-executable", QIcon(_get_fallback_pixmap()))


def _check_custom(name: str) -> QIcon | None:
    for ext in ICON_EXTENSIONS + [".jpg", ".jpeg"]:
        p = CUSTOM_ICONS_DIR / f"{name}{ext}"
        if p.is_file():
            return QIcon(str(p))
    return None


def _search_themes(icon_name: str) -> QIcon | None:
    for base_dir in ICON_THEME_DIRS:
        if not base_dir.is_dir():
            continue
        for theme in THEME_SEARCH_ORDER:
            theme_dir = base_dir / theme
            if not theme_dir.is_dir():
                continue
            for size in ICON_SIZES:
                for category in ICON_CATEGORIES:
                    for ext in ICON_EXTENSIONS:
                        candidate = theme_dir / size / category / f"{icon_name}{ext}"
                        if candidate.is_file():
                            return QIcon(str(candidate))
    return None


def _check_cache(name: str) -> QIcon | None:
    for ext in ICON_EXTENSIONS + [".jpg", ".jpeg"]:
        p = ICON_CACHE_DIR / f"{name}{ext}"
        if p.is_file():
            return QIcon(str(p))
    return None


def _cache_icon(name: str, icon: QIcon) -> None:
    """Save a resolved icon to the local cache."""
    try:
        pixmap = icon.pixmap(64, 64)
        if not pixmap.isNull():
            path = ICON_CACHE_DIR / f"{name}.png"
            pixmap.save(str(path), "PNG")
    except Exception:
        pass
