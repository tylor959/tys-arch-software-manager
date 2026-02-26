"""Main window with sidebar navigation and stacked content views."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon, QAction
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QStackedWidget, QLabel, QButtonGroup, QStatusBar, QSizePolicy,
)

from asm.app import ASMApp
from asm.ui.installed_view import InstalledView
from asm.ui.repo_browser import RepoBrowser
from asm.ui.aur_browser import AURBrowser
from asm.ui.file_installer_view import FileInstallerView
from asm.ui.flatpak_view import FlatpakView
from asm.ui.settings_view import SettingsView


NAV_ITEMS = [
    ("Installed",    "computer",          "Manage installed programs"),
    ("Repositories", "system-software-install", "Browse official repos"),
    ("AUR",          "globe",             "Browse the AUR"),
    ("Install File", "folder-open",       "Install from file"),
    ("Flatpak",      "application-x-executable", "Browse Flathub"),
    ("Settings",     "preferences-system", "App settings & tools"),
]


class MainWindow(QMainWindow):
    def __init__(self, app: ASMApp) -> None:
        super().__init__()
        self.app = app
        self.config = app.config

        self.setWindowTitle("Ty's ASM — Arch Software Manager")
        self.setMinimumSize(900, 600)
        self.resize(
            self.config.get("window_width"),
            self.config.get("window_height"),
        )

        central = QWidget()
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        root_layout = QHBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self._build_sidebar())
        root_layout.addWidget(self._build_content(), 1)

        status = QStatusBar()
        status.showMessage("Ready")
        self.setStatusBar(status)

        self._nav_buttons[0].setChecked(True)
        self._on_nav(0)

    # ── Sidebar ──
    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(2)

        title = QLabel("Ty's ASM")
        title.setObjectName("sidebarTitle")
        layout.addWidget(title)
        layout.addSpacing(8)

        self._nav_buttons: list[QPushButton] = []
        self._nav_group = QButtonGroup(self)
        self._nav_group.setExclusive(True)

        for idx, (label, icon_name, tooltip) in enumerate(NAV_ITEMS):
            btn = QPushButton(f"  {label}")
            btn.setObjectName("sidebarBtn")
            btn.setCheckable(True)
            btn.setToolTip(tooltip)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setIcon(QIcon.fromTheme(icon_name))
            btn.setIconSize(QSize(20, 20))
            self._nav_group.addButton(btn, idx)
            self._nav_buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        theme_btn = QPushButton("  Toggle Theme")
        theme_btn.setObjectName("sidebarBtn")
        theme_btn.setIcon(QIcon.fromTheme("preferences-desktop-theme"))
        theme_btn.setIconSize(QSize(20, 20))
        theme_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(theme_btn)

        version_label = QLabel("v1.0.0")
        version_label.setObjectName("appSize")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        self._nav_group.idClicked.connect(self._on_nav)
        return sidebar

    # ── Content Stack ──
    def _build_content(self) -> QWidget:
        container = QWidget()
        container.setObjectName("contentArea")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._stack = QStackedWidget()
        self._views: list[QWidget] = [
            InstalledView(self),
            RepoBrowser(self),
            AURBrowser(self),
            FileInstallerView(self),
            FlatpakView(self),
            SettingsView(self),
        ]
        for v in self._views:
            self._stack.addWidget(v)

        layout.addWidget(self._stack)
        return container

    # ── Slots ──
    def _on_nav(self, idx: int) -> None:
        self._stack.setCurrentIndex(idx)
        self.statusBar().showMessage(NAV_ITEMS[idx][2])

    def _toggle_theme(self) -> None:
        new = self.app.toggle_theme()
        self.statusBar().showMessage(f"Theme switched to {new}")

    # ── Persist window geometry ──
    def closeEvent(self, event) -> None:
        self.config.set("window_width", self.width())
        self.config.set("window_height", self.height())
        super().closeEvent(event)
