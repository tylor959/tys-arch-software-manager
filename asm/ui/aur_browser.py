"""AUR browser view — search, sort, and install from the Arch User Repository."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QGridLayout, QMessageBox, QProgressBar,
)

from asm.core.worker import TaskWorker
from asm.core.aur_client import search as aur_search, AURPackage
from asm.core import paru_backend
from asm.core.pacman_backend import is_installed
from asm.core.icon_resolver import resolve_icon
from asm.ui.widgets.app_card import AppCard
from asm.ui.widgets.progress_dialog import ProgressDialog

COLS = 2


class AURBrowser(QWidget):
    """Browse and install packages from the AUR."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[AURPackage] = []
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("AUR \u2014 Arch User Repository")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        paru_status = "paru detected" if paru_backend.is_available() else "paru not found \u2014 using AUR RPC API"
        subtitle = QLabel(f"Community-maintained packages. {paru_status}.")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("searchBar")
        self.search.setPlaceholderText("Search the AUR...")
        self.search.returnPressed.connect(self._do_search)
        toolbar.addWidget(self.search, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Votes", "Popularity", "A-Z", "Z-A", "Last Updated"])
        self.sort_combo.currentTextChanged.connect(self._apply_sort)
        toolbar.addWidget(self.sort_combo)

        layout.addLayout(toolbar)

        self._count_label = QLabel("")
        self._count_label.setObjectName("appSize")
        layout.addWidget(self._count_label)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setVisible(False)
        layout.addWidget(self._loading_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._grid_container)

        layout.addWidget(scroll, 1)

        self._placeholder = QLabel("Enter a search term to browse AUR packages.")
        self._placeholder.setObjectName("viewSubtitle")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._placeholder, 0, 0, 1, COLS)

    def _do_search(self) -> None:
        query = self.search.text().strip()
        if not query:
            return
        self._set_loading(True)
        self._worker = TaskWorker(aur_search, query)
        self._worker.finished_sig.connect(self._on_search_done)
        self._worker.start()

    def _on_search_done(self, ok: bool, data: object) -> None:
        self._set_loading(False)
        if not ok or not isinstance(data, list):
            self._show_message("AUR search failed. Check your internet connection.")
            return
        self._results = data
        self._apply_sort()

    def _apply_sort(self) -> None:
        items = list(self._results)
        mode = self.sort_combo.currentText()
        if mode == "Votes":
            items.sort(key=lambda p: p.votes, reverse=True)
        elif mode == "Popularity":
            items.sort(key=lambda p: p.popularity, reverse=True)
        elif mode == "A-Z":
            items.sort(key=lambda p: p.name.lower())
        elif mode == "Z-A":
            items.sort(key=lambda p: p.name.lower(), reverse=True)
        elif mode == "Last Updated":
            items.sort(key=lambda p: p.last_modified, reverse=True)

        self._count_label.setText(f"{len(items)} AUR packages found")
        self._populate(items)

    def _populate(self, packages: list[AURPackage]) -> None:
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not packages:
            self._show_message("No AUR packages found.")
            return

        for idx, pkg in enumerate(packages[:200]):
            installed = is_installed(pkg.name) if idx < 50 else False
            icon = resolve_icon(pkg.name)

            card = AppCard(
                name=pkg.name,
                description=pkg.description,
                icon=icon,
                installed=installed,
                votes=pkg.votes,
                popularity=pkg.popularity,
                version=pkg.version,
            )
            card.install_clicked.connect(self._on_install)
            card.remove_clicked.connect(self._on_remove)

            if pkg.out_of_date:
                card.setToolTip("This package is flagged as out-of-date")

            row, col = divmod(idx, COLS)
            self._grid_layout.addWidget(card, row, col)

    def _on_install(self, pkg_name: str) -> None:
        if paru_backend.is_available():
            reply = QMessageBox.question(
                self, "Install from AUR",
                f"Install '{pkg_name}' from the AUR via paru?\n\n"
                "This will download, build, and install the package.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                cmd = paru_backend.install_command([pkg_name])
                dlg = ProgressDialog(
                    f"Installing {pkg_name} (AUR)", cmd,
                    total_steps=100, privileged=False, parent=self,
                )
                dlg.exec()
        else:
            QMessageBox.information(
                self, "paru Required",
                "paru is not installed. Please install paru to enable AUR package installation.\n\n"
                "Run: sudo pacman -S paru",
            )

    def _on_remove(self, pkg_name: str) -> None:
        reply = QMessageBox.question(
            self, "Remove Package",
            f"Remove '{pkg_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            if paru_backend.is_available():
                cmd = paru_backend.remove_command([pkg_name])
            else:
                from asm.core.pacman_backend import remove_command
                cmd = remove_command([pkg_name])
            dlg = ProgressDialog(f"Removing {pkg_name}", cmd, total_steps=20, privileged=True, parent=self)
            dlg.exec()

    def _set_loading(self, loading: bool) -> None:
        self._loading_bar.setVisible(loading)
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if loading:
            lbl = QLabel("Searching AUR...")
            lbl.setObjectName("viewSubtitle")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._grid_layout.addWidget(lbl, 0, 0, 1, COLS)

    def _show_message(self, msg: str) -> None:
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        lbl = QLabel(msg)
        lbl.setObjectName("viewSubtitle")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(lbl, 0, 0, 1, COLS)
