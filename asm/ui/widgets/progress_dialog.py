"""Progress dialog — shows installation progress with ETA and collapsible log viewer."""

from __future__ import annotations

from PyQt6.QtCore import Qt

from asm.core.logger import get_logger

_log = get_logger("progress_dialog")
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar,
    QPushButton, QTextEdit, QSizePolicy,
)

from asm.core.worker import CommandWorker, DebInstallWorker


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
        self._worker.indeterminate_sig.connect(self._on_indeterminate)
        _log.info("ProgressDialog: starting %s", title)
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

    def _on_indeterminate(self, indeterminate: bool) -> None:
        if indeterminate:
            self._progress.setRange(0, 0)
        else:
            self._progress.setRange(0, 100)

    def _on_finished(self, ok: bool, msg: str) -> None:
        self._success = ok
        _log.info("ProgressDialog: %s", "completed" if ok else f"failed: {msg}")
        self._status_label.setText(msg)
        self._cancel_btn.setVisible(False)
        self._close_btn.setVisible(True)
        self._progress.setRange(0, 100)
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


class DebProgressDialog(QDialog):
    """Progress dialog for DEB install with step-based status updates."""

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Converting and installing .deb")
        self.setMinimumSize(520, 280)
        self.setModal(True)
        self._success = False
        self._result = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self._status_label = QLabel("Preparing...")
        self._status_label.setObjectName("appName")
        layout.addWidget(self._status_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)  # Indeterminate
        layout.addWidget(self._progress)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        self._log.setStyleSheet("font-family: monospace; font-size: 12px;")
        layout.addWidget(self._log)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._close_btn = QPushButton("Close")
        self._close_btn.setObjectName("primaryBtn")
        self._close_btn.setVisible(False)
        self._close_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._worker = DebInstallWorker(path)
        self._worker.progress_status.connect(self._on_status)
        self._worker.finished_sig.connect(self._on_finished)
        _log.info("DebProgressDialog: starting DEB install for %s", path)
        self._worker.start()

    @property
    def success(self) -> bool:
        return self._success

    @property
    def result(self):
        """InstallResult when success, or Exception when failed."""
        return self._result

    def _on_status(self, msg: str) -> None:
        self._status_label.setText(msg)
        self._log.append(msg)

    def _on_finished(self, ok: bool, data: object) -> None:
        self._success = ok
        self._result = data
        self._progress.setRange(0, 100)
        self._progress.setValue(100 if ok else 0)
        if ok:
            self._status_label.setText("Installation complete")
        else:
            msg = str(data) if isinstance(data, Exception) else getattr(data, "message", str(data))
            self._status_label.setText("Installation failed")
            self._log.append(f"Error: {msg}")
        _log.info("DebProgressDialog: %s", "completed" if ok else "failed")
        self._close_btn.setVisible(True)
