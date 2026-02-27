"""Log viewer dialog — displays app log file with refresh and copy."""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QApplication,
)

from asm.core.logger import get_log_path

TAIL_LINES = 500


class LogViewerDialog(QDialog):
    """Modal dialog to view the application log file."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ty's ASM — Log Viewer")
        self.setMinimumSize(600, 400)
        self.setModal(False)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        info = QLabel(f"Log file: {get_log_path()}")
        info.setObjectName("appSize")
        info.setWordWrap(True)
        layout.addWidget(info)

        self._text = QTextEdit()
        self._text.setReadOnly(True)
        self._text.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self._text, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._refresh)
        btn_row.addWidget(refresh_btn)

        copy_btn = QPushButton("Copy to Clipboard")
        copy_btn.setObjectName("secondaryBtn")
        copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(copy_btn)

        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._refresh()

    def _refresh(self) -> None:
        """Reload log file contents (tail of last N lines)."""
        path = get_log_path()
        if not path.exists():
            self._text.setPlainText("(Log file does not exist yet)")
            return
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            tail = lines[-TAIL_LINES:] if len(lines) > TAIL_LINES else lines
            self._text.setPlainText("".join(tail))
            self._text.verticalScrollBar().setValue(
                self._text.verticalScrollBar().maximum()
            )
        except OSError as e:
            self._text.setPlainText(f"(Could not read log: {e})")

    def _copy(self) -> None:
        """Copy log contents to clipboard."""
        text = self._text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
