"""Diagnostics dialog — shows system health results with one-click fixes."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QMessageBox,
)

from asm.core.diagnostics import run_all_checks, DiagnosticResult
from asm.core.worker import TaskWorker
from asm.ui.widgets.progress_dialog import ProgressDialog

STATUS_ICONS = {"ok": "\u2705", "warning": "\u26a0\ufe0f", "error": "\u274c"}


class DiagnosticsDialog(QDialog):
    """System diagnostics with one-click fix buttons."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("System Diagnostics")
        self.setMinimumSize(600, 420)
        self._results: list[DiagnosticResult] = []
        self._build_ui()
        self._run_checks()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("System Health Check")
        header.setObjectName("viewTitle")
        layout.addWidget(header)

        self._status_label = QLabel("Running diagnostics...")
        self._status_label.setObjectName("viewSubtitle")
        layout.addWidget(self._status_label)

        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Check", "Status", "Details", "Fix"])
        self._tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self._tree, 1)

        btn_row = QHBoxLayout()
        rerun_btn = QPushButton("Re-run Checks")
        rerun_btn.setObjectName("secondaryBtn")
        rerun_btn.clicked.connect(self._run_checks)
        btn_row.addWidget(rerun_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setObjectName("primaryBtn")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _run_checks(self) -> None:
        self._tree.clear()
        self._status_label.setText("Running diagnostics...")
        self._worker = TaskWorker(run_all_checks)
        self._worker.finished_sig.connect(self._on_results)
        self._worker.start()

    def _on_results(self, ok: bool, data: object) -> None:
        if not ok or not isinstance(data, list):
            self._status_label.setText("Diagnostics failed.")
            return

        self._results = data
        errors = sum(1 for r in data if r.status == "error")
        warnings = sum(1 for r in data if r.status == "warning")
        oks = sum(1 for r in data if r.status == "ok")
        self._status_label.setText(
            f"Results: {oks} passed, {warnings} warnings, {errors} errors"
        )

        for r in data:
            item = QTreeWidgetItem(self._tree, [
                r.name,
                STATUS_ICONS.get(r.status, "?"),
                r.message,
                "",
            ])
            if r.fix_cmd and r.fix_label:
                fix_btn = QPushButton(r.fix_label)
                fix_btn.setObjectName("secondaryBtn")
                fix_btn.clicked.connect(lambda checked, cmd=r.fix_cmd, label=r.fix_label: self._apply_fix(cmd, label))
                self._tree.setItemWidget(item, 3, fix_btn)

    def _apply_fix(self, cmd: list[str], label: str) -> None:
        reply = QMessageBox.question(
            self, "Apply Fix",
            f"Run fix: {label}?\n\nCommand: {' '.join(cmd)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            dlg = ProgressDialog(label, cmd, total_steps=20, privileged=True, parent=self)
            dlg.exec()
            self._run_checks()
