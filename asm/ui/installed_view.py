"""Installed programs view — lists GUI apps (smart filter) with management actions."""

from __future__ import annotations

import shutil
from pathlib import Path

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QCheckBox, QScrollArea, QGridLayout, QMessageBox,
    QApplication, QProgressBar,
)

from asm.core.worker import TaskWorker
from asm.core.pacman_backend import (
    list_installed_detailed, get_package_files, PackageInfo,
)
from asm.core.desktop_parser import get_all_desktop_entries, find_desktop_for_package, DesktopEntry
from asm.core.icon_resolver import resolve_icon
from asm.ui.widgets.app_card import AppCard
from asm.ui.widgets.progress_dialog import ProgressDialog
from asm.core.pacman_backend import remove_command, invalidate_pacman_cache


COLS = 2


class InstalledView(QWidget):
    """Shows installed programs with search, sort, and management controls."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._all_cards: list[dict] = []
        self._desktop_entries: dict[str, DesktopEntry] = {}
        self._data_ready = False
        self._build_ui()
        self._start_loading()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Installed Programs")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Manage your installed applications \u2014 remove, add shortcuts, and more.")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("searchBar")
        self.search.setPlaceholderText("Search installed programs...")
        toolbar.addWidget(self.search, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["A-Z", "Z-A", "Size (largest)", "Size (smallest)"])
        toolbar.addWidget(self.sort_combo)

        self.show_all = QCheckBox("Show all packages")
        self.show_all.setToolTip("Include libraries, fonts, and CLI tools")
        toolbar.addWidget(self.show_all)

        layout.addLayout(toolbar)

        # Connect signals AFTER widgets are fully built to avoid premature firing
        self.search.textChanged.connect(self._apply_filter)
        self.sort_combo.currentTextChanged.connect(self._apply_filter)
        self.show_all.toggled.connect(self._apply_filter)

        self._count_label = QLabel("")
        self._count_label.setObjectName("appSize")
        layout.addWidget(self._count_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._grid_container)

        layout.addWidget(scroll, 1)

        # Loading indicator lives OUTSIDE the grid so it can't be accidentally deleted
        self._loading_label = QLabel("Loading installed programs...")
        self._loading_label.setObjectName("viewSubtitle")
        self._loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._loading_label)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)  # indeterminate / pulsing
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setVisible(False)
        layout.addWidget(self._loading_bar)

    def _start_loading(self) -> None:
        self._data_ready = False
        self._loading_label.setVisible(True)
        self._loading_bar.setVisible(True)
        self._loading_label.setText("Loading installed programs...")
        self._worker = TaskWorker(self._load_data)
        self._worker.finished_sig.connect(self._on_loaded)
        self._worker.start()

    def _load_data(self) -> list[dict]:
        """Runs in background thread: collects all installed packages + desktop entries.

        Uses a single `pacman -Qi` call to get all package details at once
        instead of one call per package.
        """
        desktop_entries = get_all_desktop_entries()
        all_info = list_installed_detailed()
        results = []
        for name, info in all_info.items():
            desktop = find_desktop_for_package(name, desktop_entries)
            results.append({
                "info": info,
                "desktop": desktop,
                "has_desktop": desktop is not None,
            })
        return results

    def _on_loaded(self, ok: bool, data: object) -> None:
        self._loading_label.setVisible(False)
        self._loading_bar.setVisible(False)
        if not ok or not isinstance(data, list):
            self._loading_label.setText("Failed to load packages.")
            self._loading_label.setVisible(True)
            return

        self._all_cards = data
        # Build desktop_entries lookup from loaded data for shortcut actions
        self._desktop_entries = {}
        for item in data:
            desktop = item.get("desktop")
            if desktop:
                info = item["info"]
                self._desktop_entries[info.name] = desktop

        self._data_ready = True
        self._apply_filter()

    def _apply_filter(self) -> None:
        if not self._data_ready:
            return

        query = self.search.text().lower().strip()
        show_all = self.show_all.isChecked()
        sort_mode = self.sort_combo.currentText()

        filtered = []
        for item in self._all_cards:
            info: PackageInfo = item["info"]
            desktop: DesktopEntry | None = item["desktop"]

            if not show_all and not item["has_desktop"]:
                continue

            display_name = desktop.name if desktop else info.name
            if query and query not in display_name.lower() and query not in info.name.lower():
                if not (info.description and query in info.description.lower()):
                    continue

            filtered.append(item)

        if sort_mode == "A-Z":
            filtered.sort(key=lambda x: (x["desktop"].name if x["desktop"] else x["info"].name).lower())
        elif sort_mode == "Z-A":
            filtered.sort(key=lambda x: (x["desktop"].name if x["desktop"] else x["info"].name).lower(), reverse=True)
        elif sort_mode == "Size (largest)":
            filtered.sort(key=lambda x: x["info"].installed_size_bytes, reverse=True)
        elif sort_mode == "Size (smallest)":
            filtered.sort(key=lambda x: x["info"].installed_size_bytes)

        self._count_label.setText(f"{len(filtered)} programs shown")
        self._populate_grid(filtered)

    def _populate_grid(self, items: list[dict]) -> None:
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for idx, item in enumerate(items):
            info: PackageInfo = item["info"]
            desktop: DesktopEntry | None = item["desktop"]
            display_name = desktop.name if desktop else info.name
            desc = desktop.comment or info.description if desktop else info.description
            icon_name = desktop.icon if desktop else ""

            icon = resolve_icon(info.name, icon_name)

            card = AppCard(
                name=display_name,
                description=desc or "",
                size=info.installed_size or "",
                icon=icon,
                installed=True,
                version=info.version,
            )
            card.pkg_name = info.name
            card.remove_clicked.connect(self._on_remove)
            card.shortcut_clicked.connect(self._on_shortcut)
            card.info_clicked.connect(self._on_info)
            row, col = divmod(idx, COLS)
            self._grid_layout.addWidget(card, row, col)

    def _on_remove(self, pkg_name: str) -> None:
        reply = QMessageBox.question(
            self, "Remove Package",
            f"Are you sure you want to remove '{pkg_name}' and its unneeded dependencies?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = remove_command([pkg_name])
            dlg = ProgressDialog(f"Removing {pkg_name}", cmd, total_steps=20, privileged=True, parent=self)
            dlg.exec()
            if dlg.success:
                invalidate_pacman_cache()
                self._start_loading()

    def _on_info(self, pkg_name: str) -> None:
        from asm.ui.widgets.directory_browser import DirectoryBrowser
        dlg = DirectoryBrowser(pkg_name, parent=self)
        dlg.exec()

    def _on_shortcut(self, pkg_name: str) -> None:
        desktop = self._desktop_entries.get(pkg_name)
        if not desktop:
            QMessageBox.information(self, "No Desktop File", f"No .desktop file found for '{pkg_name}'.")
            return

        desktop_dir = Path.home() / "Desktop"
        desktop_dir.mkdir(exist_ok=True)
        dest = desktop_dir / Path(desktop.file_path).name

        if dest.exists():
            QMessageBox.information(self, "Shortcut Exists", f"A shortcut already exists at {dest}")
            return

        try:
            shutil.copy2(desktop.file_path, dest)
            dest.chmod(0o755)
            QMessageBox.information(self, "Shortcut Created", f"Desktop shortcut created for '{desktop.name}'.")
        except OSError as e:
            QMessageBox.warning(self, "Error", f"Failed to create shortcut: {e}")
