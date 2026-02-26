"""Configuration manager for Ty's ASM. Persists settings to ~/.config/tys-asm/settings.json."""

import json
import os
from pathlib import Path
from typing import Any

CONFIG_DIR = Path.home() / ".config" / "tys-asm"
SETTINGS_FILE = CONFIG_DIR / "settings.json"
CUSTOM_ICONS_DIR = CONFIG_DIR / "custom-icons"
CACHE_DIR = Path.home() / ".cache" / "tys-asm"
ICON_CACHE_DIR = CACHE_DIR / "icons"

DEFAULTS: dict[str, Any] = {
    "theme": "dark",
    "default_sort": "a-z",
    "auto_desktop_shortcut": False,
    "default_install_disk": "/",
    "show_all_packages": False,
    "window_width": 1100,
    "window_height": 720,
    "sidebar_collapsed": False,
    "installed_sort": "a-z",
    "repo_sort": "a-z",
    "aur_sort": "votes",
    "flatpak_sort": "a-z",
}


class Config:
    """Singleton settings manager with JSON persistence."""

    _instance: "Config | None" = None

    def __new__(cls) -> "Config":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
        return cls._instance

    def __init__(self) -> None:
        if self._loaded:
            return
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._ensure_dirs()
        self._load()
        self._loaded = True

    @staticmethod
    def _ensure_dirs() -> None:
        for d in (CONFIG_DIR, CUSTOM_ICONS_DIR, CACHE_DIR, ICON_CACHE_DIR):
            d.mkdir(parents=True, exist_ok=True)

    def _load(self) -> None:
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        try:
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def get(self, key: str, fallback: Any = None) -> Any:
        return self._data.get(key, fallback if fallback is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()

    def reset(self) -> None:
        self._data = dict(DEFAULTS)
        self.save()
