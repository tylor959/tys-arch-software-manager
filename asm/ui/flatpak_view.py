"""Flatpak view — browse Flathub, manage installed Flatpak apps, auto-setup."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QGridLayout, QPushButton, QMessageBox,
    QTabWidget, QProgressBar,
)

from asm.core import flatpak_backend
from asm.core.worker import TaskWorker
from asm.core.icon_resolver import resolve_icon
from asm.ui.widgets.app_card import AppCard
from asm.ui.widgets.progress_dialog import ProgressDialog

COLS = 2


class FlatpakView(QWidget):
    """Browse Flathub, install/remove Flatpak apps."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._search_results: list[flatpak_backend.FlatpakApp] = []
        self._installed_results: list[flatpak_backend.FlatpakApp] = []
        self._build_ui()
        self._check_flatpak()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Flatpak \u2014 Flathub")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        self._status_label = QLabel("Checking Flatpak installation...")
        self._status_label.setObjectName("viewSubtitle")
        layout.addWidget(self._status_label)

        # Setup panel (hidden when flatpak is ready)
        self._setup_panel = QWidget()
        setup_layout = QVBoxLayout(self._setup_panel)
        setup_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setup_msg = QLabel("Flatpak is not installed or Flathub is not configured.")
        setup_msg.setObjectName("viewSubtitle")
        setup_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setup_layout.addWidget(setup_msg)

        setup_btn_row = QHBoxLayout()
        setup_btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._install_flatpak_btn = QPushButton("Install Flatpak")
        self._install_flatpak_btn.setObjectName("primaryBtn")
        self._install_flatpak_btn.clicked.connect(self._install_flatpak)
        setup_btn_row.addWidget(self._install_flatpak_btn)
        self._add_flathub_btn = QPushButton("Add Flathub")
        self._add_flathub_btn.setObjectName("primaryBtn")
        self._add_flathub_btn.clicked.connect(self._add_flathub)
        setup_btn_row.addWidget(self._add_flathub_btn)
        setup_layout.addLayout(setup_btn_row)

        self._setup_panel.setVisible(False)
        layout.addWidget(self._setup_panel)

        # Main content (hidden until flatpak is ready)
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        # Browse tab
        browse_widget = QWidget()
        browse_layout = QVBoxLayout(browse_widget)
        browse_layout.setContentsMargins(0, 8, 0, 0)

        browse_toolbar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setObjectName("searchBar")
        self.search.setPlaceholderText("Search Flathub...")
        self.search.returnPressed.connect(self._do_search)
        browse_toolbar.addWidget(self.search, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["A-Z", "Z-A"])
        self.sort_combo.currentTextChanged.connect(self._apply_search_sort)
        browse_toolbar.addWidget(self.sort_combo)

        browse_layout.addLayout(browse_toolbar)

        self._search_count = QLabel("")
        self._search_count.setObjectName("appSize")
        browse_layout.addWidget(self._search_count)

        self._search_loading_bar = QProgressBar()
        self._search_loading_bar.setRange(0, 0)
        self._search_loading_bar.setFixedHeight(4)
        self._search_loading_bar.setTextVisible(False)
        self._search_loading_bar.setVisible(False)
        browse_layout.addWidget(self._search_loading_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._search_grid_container = QWidget()
        self._search_grid = QGridLayout(self._search_grid_container)
        self._search_grid.setSpacing(12)
        self._search_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._search_grid_container)
        browse_layout.addWidget(scroll, 1)

        self._tabs.addTab(browse_widget, "Browse Flathub")

        # Installed tab
        installed_widget = QWidget()
        installed_layout = QVBoxLayout(installed_widget)
        installed_layout.setContentsMargins(0, 8, 0, 0)

        refresh_row = QHBoxLayout()
        refresh_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._load_installed)
        refresh_row.addWidget(refresh_btn)
        update_btn = QPushButton("Update All")
        update_btn.setObjectName("primaryBtn")
        update_btn.clicked.connect(self._update_all)
        refresh_row.addWidget(update_btn)
        installed_layout.addLayout(refresh_row)

        self._installed_count = QLabel("")
        self._installed_count.setObjectName("appSize")
        installed_layout.addWidget(self._installed_count)

        self._installed_loading_bar = QProgressBar()
        self._installed_loading_bar.setRange(0, 0)
        self._installed_loading_bar.setFixedHeight(4)
        self._installed_loading_bar.setTextVisible(False)
        self._installed_loading_bar.setVisible(False)
        installed_layout.addWidget(self._installed_loading_bar)

        iscroll = QScrollArea()
        iscroll.setWidgetResizable(True)
        iscroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._installed_grid_container = QWidget()
        self._installed_grid = QGridLayout(self._installed_grid_container)
        self._installed_grid.setSpacing(12)
        self._installed_grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        iscroll.setWidget(self._installed_grid_container)
        installed_layout.addWidget(iscroll, 1)

        self._tabs.addTab(installed_widget, "Installed")

        content_layout.addWidget(self._tabs)
        self._content.setVisible(False)
        layout.addWidget(self._content, 1)

    def _check_flatpak(self) -> None:
        if not flatpak_backend.is_available():
            self._status_label.setText("Flatpak is not installed.")
            self._setup_panel.setVisible(True)
            self._install_flatpak_btn.setVisible(True)
            self._add_flathub_btn.setVisible(False)
        elif not flatpak_backend.has_flathub():
            self._status_label.setText("Flatpak is installed but Flathub remote is missing.")
            self._setup_panel.setVisible(True)
            self._install_flatpak_btn.setVisible(False)
            self._add_flathub_btn.setVisible(True)
        else:
            self._status_label.setText("Search Flathub or manage your installed Flatpak apps.")
            self._setup_panel.setVisible(False)
            self._content.setVisible(True)
            self._load_installed()

    def _install_flatpak(self) -> None:
        from asm.core.pacman_backend import install_command
        cmd = install_command(["flatpak"])
        dlg = ProgressDialog("Installing Flatpak", cmd, total_steps=20, privileged=True, parent=self)
        dlg.exec()
        if dlg.success:
            self._check_flatpak()

    def _add_flathub(self) -> None:
        cmd = flatpak_backend.setup_flathub_command()
        dlg = ProgressDialog("Adding Flathub remote", cmd, total_steps=10, privileged=True, parent=self)
        dlg.exec()
        if dlg.success:
            self._check_flatpak()

    def _do_search(self) -> None:
        query = self.search.text().strip()
        if not query:
            return
        self._search_loading_bar.setVisible(True)
        self._set_grid_loading(self._search_grid, True)
        self._worker = TaskWorker(flatpak_backend.search_flathub_api, query)
        self._worker.finished_sig.connect(self._on_search_done)
        self._worker.start()

    def _on_search_done(self, ok: bool, data: object) -> None:
        self._search_loading_bar.setVisible(False)
        self._set_grid_loading(self._search_grid, False)
        if not ok or not isinstance(data, list):
            return
        self._search_results = data
        self._apply_search_sort()

    def _apply_search_sort(self) -> None:
        items = list(self._search_results)
        mode = self.sort_combo.currentText()
        if mode == "A-Z":
            items.sort(key=lambda a: a.name.lower())
        elif mode == "Z-A":
            items.sort(key=lambda a: a.name.lower(), reverse=True)

        self._search_count.setText(f"{len(items)} apps found")
        self._populate_grid(self._search_grid, items)

    def _load_installed(self) -> None:
        self._installed_loading_bar.setVisible(True)
        self._worker2 = TaskWorker(flatpak_backend.list_installed)
        self._worker2.finished_sig.connect(self._on_installed_loaded)
        self._worker2.start()

    def _on_installed_loaded(self, ok: bool, data: object) -> None:
        self._installed_loading_bar.setVisible(False)
        if not ok or not isinstance(data, list):
            return
        self._installed_results = data
        self._installed_count.setText(f"{len(data)} Flatpak apps installed")
        self._populate_grid(self._installed_grid, data)

    def _populate_grid(self, grid: QGridLayout, apps: list[flatpak_backend.FlatpakApp]) -> None:
        while grid.count():
            child = grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not apps:
            lbl = QLabel("No apps found.")
            lbl.setObjectName("viewSubtitle")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, 0, 1, COLS)
            return

        for idx, app in enumerate(apps[:200]):
            icon = resolve_icon(app.app_id.split(".")[-1] if app.app_id else app.name)
            card = AppCard(
                name=app.name or app.app_id,
                description=app.description,
                size=app.installed_size or app.origin,
                icon=icon,
                installed=app.is_installed,
                version=app.version,
            )
            card.pkg_name = app.app_id
            card.install_clicked.connect(self._on_install)
            card.remove_clicked.connect(self._on_remove)
            row, col = divmod(idx, COLS)
            grid.addWidget(card, row, col)

    def _on_install(self, app_id: str) -> None:
        reply = QMessageBox.question(
            self, "Install Flatpak",
            f"Install '{app_id}' from Flathub?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = flatpak_backend.install_command(app_id)
            dlg = ProgressDialog(f"Installing {app_id}", cmd, total_steps=50, privileged=False, parent=self)
            dlg.exec()
            if dlg.success:
                self._load_installed()

    def _on_remove(self, app_id: str) -> None:
        reply = QMessageBox.question(
            self, "Remove Flatpak",
            f"Remove '{app_id}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = flatpak_backend.remove_command(app_id)
            dlg = ProgressDialog(f"Removing {app_id}", cmd, total_steps=20, privileged=False, parent=self)
            dlg.exec()
            if dlg.success:
                self._load_installed()

    def _update_all(self) -> None:
        cmd = flatpak_backend.update_command()
        dlg = ProgressDialog("Updating all Flatpak apps", cmd, total_steps=50, privileged=False, parent=self)
        dlg.exec()
        self._load_installed()

    @staticmethod
    def _set_grid_loading(grid: QGridLayout, loading: bool) -> None:
        while grid.count():
            child = grid.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if loading:
            lbl = QLabel("Searching...")
            lbl.setObjectName("viewSubtitle")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, 0, 1, COLS)
