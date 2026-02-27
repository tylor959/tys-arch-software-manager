"""Repository browser view — search and install from official Arch repos with categories."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QComboBox, QScrollArea, QGridLayout, QListWidget, QSplitter,
    QMessageBox, QListWidgetItem, QProgressBar,
)

from asm.core.worker import TaskWorker
from asm.core.pacman_backend import (
    search_repos, get_groups, get_group_packages, install_command,
    PackageInfo, is_installed, invalidate_pacman_cache,
)
from asm.core.pkgstats import get_popularity_batch
from asm.core.icon_resolver import resolve_icon
from asm.ui.widgets.app_card import AppCard
from asm.ui.widgets.progress_dialog import ProgressDialog


CATEGORY_MAP = {
    "All":          None,
    "Internet":     ["firefox", "chromium", "thunderbird", "network"],
    "Multimedia":   ["multimedia", "audio", "video", "pulseaudio", "pipewire"],
    "Games":        ["games"],
    "Development":  ["devel", "base-devel"],
    "Graphics":     ["graphics", "gimp"],
    "Office":       ["office", "libreoffice"],
    "System":       ["system", "base", "systemd"],
    "Science":      ["science"],
    "Fonts":        ["fonts"],
    "Utilities":    ["utils", "xorg", "wayland"],
    "KDE/Plasma":   ["kde-applications", "plasma"],
    "GNOME":        ["gnome", "gnome-extra"],
}

COLS = 2


class RepoBrowser(QWidget):
    """Browse and install packages from official repositories."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._results: list[PackageInfo] = []
        self._popularity: dict[str, float] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Repositories")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Search and install software from official Arch Linux repositories.")
        subtitle.setObjectName("viewSubtitle")
        layout.addWidget(subtitle)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.search = QLineEdit()
        self.search.setObjectName("searchBar")
        self.search.setPlaceholderText("Search repositories...")
        self.search.returnPressed.connect(self._do_search)
        toolbar.addWidget(self.search, 1)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["A-Z", "Z-A", "Popularity", "Repository"])
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

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self.category_list = QListWidget()
        self.category_list.setObjectName("categoryList")
        for cat in CATEGORY_MAP:
            self.category_list.addItem(cat)
        self.category_list.setFixedWidth(160)
        self.category_list.setCurrentRow(0)
        self.category_list.currentTextChanged.connect(self._on_category)
        splitter.addWidget(self.category_list)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(12)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self._grid_container)
        splitter.addWidget(scroll)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        layout.addWidget(splitter, 1)

        self._placeholder = QLabel("Search for packages or pick a category to get started.")
        self._placeholder.setObjectName("viewSubtitle")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._grid_layout.addWidget(self._placeholder, 0, 0, 1, COLS)

    def _do_search(self) -> None:
        query = self.search.text().strip()
        if not query:
            return
        self._set_loading(True)
        self._worker = TaskWorker(self._search_with_popularity, query)
        self._worker.finished_sig.connect(self._on_search_done)
        self._worker.start()

    @staticmethod
    def _search_with_popularity(query: str) -> tuple[list[PackageInfo], dict[str, float]]:
        results = search_repos(query)
        names = [p.name for p in results[:200]]
        popularity = get_popularity_batch(names) if names else {}
        return results, popularity

    def _on_category(self, category: str) -> None:
        groups = CATEGORY_MAP.get(category)
        if groups is None:
            return
        if not groups:
            return
        self._set_loading(True)
        self._worker = TaskWorker(self._search_category, groups)
        self._worker.finished_sig.connect(self._on_search_done)
        self._worker.start()

    @staticmethod
    def _search_category(groups: list[str]) -> tuple[list[PackageInfo], dict[str, float]]:
        results = []
        seen: set[str] = set()
        for g in groups:
            for pkg in search_repos(g):
                if pkg.name not in seen:
                    seen.add(pkg.name)
                    results.append(pkg)
        names = [p.name for p in results[:200]]
        popularity = get_popularity_batch(names) if names else {}
        return results, popularity

    def _on_search_done(self, ok: bool, data: object) -> None:
        self._set_loading(False)
        if not ok:
            self._show_message("Search failed. Check your connection.")
            return
        if isinstance(data, tuple) and len(data) == 2:
            self._results, self._popularity = data
        elif isinstance(data, list):
            self._results = data
            self._popularity = {}
        else:
            self._show_message("Search failed. Check your connection.")
            return
        self._apply_sort()

    def _apply_sort(self) -> None:
        items = list(self._results)
        mode = self.sort_combo.currentText()
        if mode == "A-Z":
            items.sort(key=lambda p: p.name.lower())
        elif mode == "Z-A":
            items.sort(key=lambda p: p.name.lower(), reverse=True)
        elif mode == "Popularity":
            items.sort(key=lambda p: self._popularity.get(p.name, 0), reverse=True)
        elif mode == "Repository":
            items.sort(key=lambda p: (p.repository, p.name.lower()))

        self._count_label.setText(f"{len(items)} packages found")
        self._populate(items)

    def _populate(self, packages: list[PackageInfo]) -> None:
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not packages:
            self._show_message("No packages found.")
            return

        for idx, pkg in enumerate(packages[:200]):
            icon = resolve_icon(pkg.name)
            pop = self._popularity.get(pkg.name)
            card = AppCard(
                name=pkg.name,
                description=pkg.description,
                size=pkg.repository,
                icon=icon,
                installed=pkg.is_installed,
                version=pkg.version,
                popularity=pop,
            )
            card.install_clicked.connect(self._on_install)
            card.remove_clicked.connect(self._on_remove)
            row, col = divmod(idx, COLS)
            self._grid_layout.addWidget(card, row, col)

    def _on_install(self, pkg_name: str) -> None:
        reply = QMessageBox.question(
            self, "Install Package",
            f"Install '{pkg_name}' from official repositories?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = install_command([pkg_name])
            dlg = ProgressDialog(f"Installing {pkg_name}", cmd, total_steps=30, privileged=True, parent=self)
            dlg.exec()
            if dlg.success:
                invalidate_pacman_cache()
                self._do_search()

    def _on_remove(self, pkg_name: str) -> None:
        from asm.core.pacman_backend import remove_command
        reply = QMessageBox.question(
            self, "Remove Package",
            f"Remove '{pkg_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            cmd = remove_command([pkg_name])
            dlg = ProgressDialog(f"Removing {pkg_name}", cmd, total_steps=20, privileged=True, parent=self)
            dlg.exec()
            if dlg.success:
                invalidate_pacman_cache()
                self._do_search()

    def _set_loading(self, loading: bool) -> None:
        self._loading_bar.setVisible(loading)
        while self._grid_layout.count():
            child = self._grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if loading:
            lbl = QLabel("Searching...")
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
