"""Directory browser dialog — shows all files owned by a package, grouped by type."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QPushButton, QHeaderView, QMessageBox,
)

from asm.core.pacman_backend import get_package_files


FILE_GROUPS = {
    "Binaries":       ["/usr/bin/", "/usr/local/bin/", "/bin/"],
    "Libraries":      ["/usr/lib/", "/usr/local/lib/", "/lib/"],
    "Configuration":  ["/etc/"],
    "Data":           ["/usr/share/"],
    "Documentation":  ["/usr/share/doc/", "/usr/share/man/", "/usr/share/info/"],
    "Other":          [],
}


class DirectoryBrowser(QDialog):
    """Shows the file tree for a package with open-in-file-manager actions."""

    def __init__(self, pkg_name: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Files owned by {pkg_name}")
        self.setMinimumSize(600, 450)
        self.pkg_name = pkg_name
        self._build_ui()
        self._load_files()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel(f"Install directories for: {self.pkg_name}")
        header.setObjectName("appName")
        layout.addWidget(header)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Path", "Size"])
        self._tree.header().setStretchLastSection(False)
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree, 1)

        self._count_label = QLabel("")
        self._count_label.setObjectName("appSize")
        layout.addWidget(self._count_label)

        btn_row = QHBoxLayout()
        open_btn = QPushButton("Open Selected in File Manager")
        open_btn.setObjectName("secondaryBtn")
        open_btn.clicked.connect(self._open_selected)
        btn_row.addWidget(open_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _load_files(self) -> None:
        files = get_package_files(self.pkg_name)
        if not files:
            self._count_label.setText("No files found for this package.")
            return

        grouped: dict[str, list[str]] = {g: [] for g in FILE_GROUPS}
        for f in files:
            placed = False
            for group, prefixes in FILE_GROUPS.items():
                if group == "Other":
                    continue
                for prefix in prefixes:
                    if f.startswith(prefix):
                        grouped[group].append(f)
                        placed = True
                        break
                if placed:
                    break
            if not placed:
                grouped["Other"].append(f)

        total = 0
        for group, group_files in grouped.items():
            if not group_files:
                continue
            parent = QTreeWidgetItem(self._tree, [f"{group} ({len(group_files)} files)", ""])
            parent.setExpanded(False)
            for fp in sorted(group_files):
                size = ""
                try:
                    if os.path.isfile(fp):
                        sz = os.path.getsize(fp)
                        total += sz
                        if sz > 1024 * 1024:
                            size = f"{sz / (1024*1024):.1f} MiB"
                        elif sz > 1024:
                            size = f"{sz / 1024:.1f} KiB"
                        else:
                            size = f"{sz} B"
                except OSError:
                    pass
                QTreeWidgetItem(parent, [fp, size])

        if total > 1024 * 1024:
            total_str = f"{total / (1024*1024):.1f} MiB"
        elif total > 1024:
            total_str = f"{total / 1024:.1f} KiB"
        else:
            total_str = f"{total} B"
        self._count_label.setText(f"{len(files)} files, {total_str} total")

    def _open_selected(self) -> None:
        item = self._tree.currentItem()
        if not item or item.childCount() > 0:
            QMessageBox.information(self, "Select a File", "Select a specific file path to open its directory.")
            return
        path = item.text(0)
        directory = str(Path(path).parent)
        try:
            subprocess.Popen(["xdg-open", directory])
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not open file manager: {e}")
