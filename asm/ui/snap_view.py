"""Snap view — browse Snap Store, install/remove Snap packages."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QGridLayout, QMessageBox, QProgressBar,
    QPushButton,
)

from asm.core.worker import TaskWorker
from asm.core import snap_backend
from asm.core.icon_resolver import resolve_icon
from asm.ui.widgets.app_card import AppCard
from asm.ui.widgets.progress_dialog import ProgressDialog

COLS = 2


class SnapView(QWidget):
    """Browse and install Snap packages from the Snap Store."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[snap_backend.SnapApp] = []
        self._build_ui()
        self._check_snap()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Snap")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        self._status_label = QLabel("Checking Snap installation...")
        self._status_label.setObjectName("viewSubtitle")
        layout.addWidget(self._status_label)

        # Setup panel (hidden when snap is ready)
        self._setup_panel = QWidget()
        setup_layout = QVBoxLayout(self._setup_panel)
        setup_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setup_msg = QLabel(
            "Snap is not installed. On Arch Linux, install snapd from the AUR:\n\n"
            "paru -S snapd\n\n"
            "Then enable the snapd.socket and reboot, or run: sudo systemctl enable --now snapd.socket"
        )
        setup_msg.setObjectName("viewSubtitle")
        setup_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        setup_msg.setWordWrap(True)
        setup_layout.addWidget(setup_msg)

        self._install_snapd_btn = QPushButton("Install snapd (via paru)")
        self._install_snapd_btn.setObjectName("primaryBtn")
        self._install_snapd_btn.clicked.connect(self._install_snapd)
        setup_layout.addWidget(self._install_snapd_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._setup_panel.setVisible(False)
        layout.addWidget(self._setup_panel)

        # Main content (hidden until snap is ready)
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 8, 0, 0)

        snap_status = "snap detected" if snap_backend.is_available() else "snap not found"
        subtitle = QLabel(f"Search and install from the Snap Store. {snap_status}.")
        subtitle.setObjectName("viewSubtitle")
        content_layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("searchBar")
        self.search.setPlaceholderText("Search Snap packages...")
        self.search.returnPressed.connect(self._do_search)
        toolbar.addWidget(self.search, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["A-Z", "Z-A", "Version"])
        self.sort_combo.currentTextChanged.connect(self._apply_sort)
        toolbar.addWidget(self.sort_combo)

        content_layout.addLayout(toolbar)

        self._count_label = QLabel("")
        self._count_label.setObjectName("appSize")
        content_layout.addWidget(self._count_label)

        self._loading_bar = QProgressBar()
        self._loading_bar.setRange(0, 0)
        self._loading_bar.setFixedHeight(4)
        self._loading_bar.setTextVisible(False)
        self._loading_bar.setVisible(False)
        content_layout.addWidget(self._loading_bar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._grid_container)

        content_layout.addWidget(scroll, 1)

        self._placeholder = QLabel("Enter a search term to browse Snap packages.")
        self._placeholder.setObjectName("viewSubtitle")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._placeholder, 0, 0, 1, COLS)

        self._content.setVisible(False)
        layout.addWidget(self._content)

    def _check_snap(self) -> None:
        if snap_backend.is_available():
            self._status_label.setText("Snap is ready. Search for packages above.")
            self._setup_panel.setVisible(False)
            self._content.setVisible(True)
        else:
            self._status_label.setText("Snap is not installed.")
            self._setup_panel.setVisible(True)
            self._content.setVisible(False)

    def _install_snapd(self) -> None:
        from asm.core.pacman_backend import install_paru_command
        cmd = snap_backend.install_snapd_command()
        if not cmd:
            # Auto-install paru from official repos, then retry
            dlg1 = ProgressDialog(
                "Installing paru (AUR helper)",
                install_paru_command(),
                total_steps=10,
                privileged=True,
                parent=self,
            )
            dlg1.exec()
            if not dlg1.success:
                QMessageBox.warning(
                    self, "Installation Failed",
                    "Could not install paru. snapd requires an AUR helper.\n\n"
                    "Try manually: sudo pacman -S paru",
                )
                return
            cmd = snap_backend.install_snapd_command()
        if cmd:
            dlg = ProgressDialog("Installing snapd", cmd, total_steps=50, privileged=False, parent=self)
            dlg.exec()
            if dlg.success:
                self._check_snap()
                QMessageBox.information(
                    self, "Snap Installed",
                    "snapd was installed. You may need to enable the socket and reboot:\n\n"
                    "sudo systemctl enable --now snapd.socket\n\n"
                    "Then log out and back in, or reboot.",
                )

    def _do_search(self) -> None:
        query = self.search.text().strip()
        if not query:
            return
        self._set_loading(True)
        self._worker = TaskWorker(snap_backend.search, query)
        self._worker.finished_sig.connect(self._on_search_done)
        self._worker.start()

    def _on_search_done(self, ok: bool, data: object) -> None:
        self._set_loading(False)
        if not ok or not isinstance(data, list):
            self._show_message("Snap search failed. Check your internet connection.")
            return
        self._results = data
        self._apply_sort()

    def _apply_sort(self) -> None:
        items = list(self._results)
        mode = self.sort_combo.currentText()
        if mode == "A-Z":
            items.sort(key=lambda p: p.name.lower())
        elif mode == "Z-A":
            items.sort(key=lambda p: p.name.lower(), reverse=True)
        elif mode == "Version":
            items.sort(key=lambda p: p.version or "", reverse=True)

        self._count_label.setText(f"{len(items)} Snap packages found")
        self._populate(items)

    def _populate(self, packages: list[snap_backend.SnapApp]) -> None:
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not packages:
            self._show_message("No Snap packages found.")
            return

        for idx, app in enumerate(packages[:200]):
            icon = resolve_icon(app.name)

            card = AppCard(
                name=app.name,
                description=app.summary,
                icon=icon,
                installed=app.is_installed,
                version=app.installed_version or app.version,
            )
            card.pkg_name = app.name
            card.install_clicked.connect(self._on_install)
            card.remove_clicked.connect(self._on_remove)

            row, col = divmod(idx, COLS)
            self._grid_layout.addWidget(card, row, col)

    def _on_install(self, name: str) -> None:
        reply = QMessageBox.question(
            self, "Install Snap",
            f"Install '{name}' from the Snap Store?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = snap_backend.install_command(name)
            dlg = ProgressDialog(f"Installing {name}", cmd, total_steps=30, privileged=True, parent=self)
            dlg.exec()
            if dlg.success:
                self._do_search()

    def _on_remove(self, name: str) -> None:
        reply = QMessageBox.question(
            self, "Remove Snap",
            f"Remove '{name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = snap_backend.remove_command(name)
            dlg = ProgressDialog(f"Removing {name}", cmd, total_steps=20, privileged=True, parent=self)
            dlg.exec()
            if dlg.success:
                self._do_search()

    def _set_loading(self, loading: bool) -> None:
        self._loading_bar.setVisible(loading)
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if loading:
            lbl = QLabel("Searching Snap Store...")
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
