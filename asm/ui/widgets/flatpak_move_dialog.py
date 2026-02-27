"""Dialog to move a Flatpak app to a different installation (disk)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QMessageBox,
)

from asm.core import flatpak_backend


class FlatpakMoveDialog(QDialog):
    """Dialog to select target installation and move a Flatpak app."""

    def __init__(self, app_id: str, app_name: str, parent=None) -> None:
        super().__init__(parent)
        self.app_id = app_id
        self.app_name = app_name
        self._target_installation: str | None = None
        self.setWindowTitle(f"Move {app_name} to Different Disk")
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        layout.addWidget(QLabel(f"Move '{app_name}' to a different installation:"))
        layout.addWidget(QLabel("Select target installation (disk):"))

        self._combo = QComboBox()
        installations = flatpak_backend.list_installations()
        current = flatpak_backend.get_installation_for_app(app_id)

        for inst in installations:
            label = f"{inst.display_name} — {inst.path}"
            if inst.id == current:
                label += " (current)"
            self._combo.addItem(label, inst.id)

        layout.addWidget(self._combo)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("secondaryBtn")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        move_btn = QPushButton("Move")
        move_btn.setObjectName("primaryBtn")
        move_btn.clicked.connect(self._on_move)
        btn_row.addWidget(move_btn)
        layout.addLayout(btn_row)

    def _on_move(self) -> None:
        target = self._combo.currentData()
        current = flatpak_backend.get_installation_for_app(self.app_id)
        if target == current:
            QMessageBox.warning(
                self, "Same Location",
                f"'{self.app_name}' is already in this installation.",
            )
            return
        self._target_installation = target
        self.accept()

    def get_target_installation(self) -> str | None:
        """Return the selected target installation id."""
        return self._target_installation
