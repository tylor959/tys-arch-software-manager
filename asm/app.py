"""QApplication subclass handling theme initialization and single-instance locking."""

import sys
from pathlib import Path

from PyQt6.QtCore import QLockFile, QStandardPaths
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from asm import __app_name__, __version__
from asm.core.config import Config


THEMES_DIR = Path(__file__).parent / "themes"


class ASMApp(QApplication):
    """Main application for Ty's ASM."""

    def __init__(self, argv: list[str]) -> None:
        super().__init__(argv)
        self.setApplicationName(__app_name__)
        self.setApplicationVersion(__version__)
        self.setDesktopFileName("tys-asm")

        assets = Path(__file__).parent / "assets"
        logo = assets / "logo.svg"
        if logo.exists():
            self.setWindowIcon(QIcon(str(logo)))

        self.config = Config()
        self.apply_theme(self.config.get("theme"))

    # ── Lock file for single instance ──
    def acquire_lock(self) -> bool:
        tmp = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.TempLocation)
        self._lock = QLockFile(f"{tmp}/tys-asm.lock")
        return self._lock.tryLock(100)

    # ── Theme management ──
    def apply_theme(self, theme_name: str) -> None:
        qss_file = THEMES_DIR / f"{theme_name}.qss"
        if not qss_file.exists():
            qss_file = THEMES_DIR / "dark.qss"
        try:
            self.setStyleSheet(qss_file.read_text())
        except OSError:
            pass

    def toggle_theme(self) -> str:
        current = self.config.get("theme")
        new_theme = "light" if current == "dark" else "dark"
        self.config.set("theme", new_theme)
        self.apply_theme(new_theme)
        return new_theme
