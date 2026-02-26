"""Progress dialog — shows installation progress with ETA and collapsible log viewer."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QSizePolicy,
)

from asm.core.worker import CommandWorker


class ProgressDialog(QDialog):
    """Modal progress dialog for package operations."""

    def __init__(
        self,
        title: str,
        cmd: list[str],
        total_steps: int = 50,
        privileged: bool = True,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(520, 300)
        self.setModal(True)
        self._success = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._status_label = QLabel("Preparing...")
        self._status_label.setObjectName("appName")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        layout.addWidget(self._progress)

        eta_row = QHBoxLayout()
        self._eta_label = QLabel("")
        self._eta_label.setObjectName("appSize")
        eta_row.addWidget(self._eta_label)
        eta_row.addStretch()
        self._pct_label = QLabel("0%")
        self._pct_label.setObjectName("appSize")
        eta_row.addWidget(self._pct_label)
        layout.addLayout(eta_row)

        toggle_btn = QPushButton("Show Log")
        toggle_btn.setObjectName("secondaryBtn")
        toggle_btn.setCheckable(True)
        toggle_btn.toggled.connect(self._toggle_log)
        layout.addWidget(toggle_btn)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setVisible(False)
        self._log.setMaximumHeight(180)
        self._log.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setObjectName("dangerBtn")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("primaryBtn")
        self._close_btn.setVisible(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._worker = CommandWorker(cmd, total_steps=total_steps, privileged=privileged)
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.log_line.connect(self._on_log)
        self._worker.eta.connect(self._on_eta)
        self._worker.finished_sig.connect(self._on_finished)
        self._worker.start()

    @property
    def success(self) -> bool:
        return self._success

    def _on_progress(self, pct: int) -> None:
        self._progress.setValue(pct)
        self._pct_label.setText(f"{pct}%")

    def _on_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _on_log(self, line: str) -> None:
        self._log.append(line)

    def _on_eta(self, eta: str) -> None:
        self._eta_label.setText(eta)

    def _on_finished(self, ok: bool, msg: str) -> None:
        self._success = ok
        self._status_label.setText(msg)
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)
        if ok:
            self._progress.setValue(100)
            self._pct_label.setText("100%")
            self._eta_label.setText("Done")

    def _on_cancel(self) -> None:
        self._worker.cancel()
        self._status_label.setText("Cancelling...")

    def _toggle_log(self, visible: bool) -> None:
        self._log.setVisible(visible)
        self.adjustSize()
