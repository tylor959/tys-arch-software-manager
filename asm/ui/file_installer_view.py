"""File installer view — drag-and-drop zone for installing from local files.

Supports .deb, .rpm, .tar.gz, .tar.zst, .AppImage, .flatpak with
self-diagnosis, missing tool detection, and progress tracking.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFileDialog,
    QMessageBox, QGroupBox, QFormLayout, QProgressBar,
)

from asm.core.file_installer import (
    analyze_file, detect_file_type, FileType, FileAnalysis,
    install_appimage, install_rpm, install_flatpak_file,
)
from asm.core.logger import get_logger
from asm.core.pacman_backend import invalidate_pacman_cache

_log = get_logger("file_installer_view")
from asm.core import flatpak_backend
from asm.core.worker import TaskWorker
from asm.ui.widgets.progress_dialog import DebProgressDialog, ProgressDialog


class FileInstallerView(QWidget):
    """Install software from local files with full diagnostics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self._current_analysis: FileAnalysis | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Install from File")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        subtitle = QLabel("Drag and drop a file, or browse to select one. "
                          "Supports .deb, .rpm, .tar.gz, .tar.zst, .AppImage, and .flatpak.")
        subtitle.setObjectName("viewSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        layout.addStretch()

        self.drop_label = QLabel("Drop file here\n\nor click Browse below")
        self.drop_label.setObjectName("dropZone")
        self.drop_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_label.setMinimumHeight(160)
        layout.addWidget(self.drop_label)

        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.browse_btn = QPushButton("Browse Files")
        self.browse_btn.setObjectName("primaryBtn")
        self.browse_btn.clicked.connect(self._browse)
        btn_row.addWidget(self.browse_btn)
        layout.addLayout(btn_row)

        self._analysis_bar = QProgressBar()
        self._analysis_bar.setRange(0, 0)
        self._analysis_bar.setFixedHeight(4)
        self._analysis_bar.setTextVisible(False)
        self._analysis_bar.setVisible(False)
        layout.addWidget(self._analysis_bar)

        # Analysis panel (hidden until file selected)
        self._analysis_group = QGroupBox("File Analysis")
        analysis_form = QFormLayout(self._analysis_group)
        analysis_form.setSpacing(8)

        self._file_label = QLabel("")
        analysis_form.addRow("File:", self._file_label)
        self._type_label = QLabel("")
        analysis_form.addRow("Type:", self._type_label)
        self._size_label = QLabel("")
        analysis_form.addRow("Size:", self._size_label)
        self._action_label = QLabel("")
        self._action_label.setWordWrap(True)
        analysis_form.addRow("Action:", self._action_label)
        self._build_label = QLabel("")
        analysis_form.addRow("Build system:", self._build_label)
        self._tools_label = QLabel("")
        self._tools_label.setWordWrap(True)
        analysis_form.addRow("Missing tools:", self._tools_label)

        self._analysis_group.setVisible(False)
        layout.addWidget(self._analysis_group)

        # Action buttons
        action_row = QHBoxLayout()
        action_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._install_btn = QPushButton("Install")
        self._install_btn.setObjectName("primaryBtn")
        self._install_btn.setVisible(False)
        self._install_btn.clicked.connect(self._do_install)
        action_row.addWidget(self._install_btn)

        self._fix_btn = QPushButton("Install Missing Tools")
        self._fix_btn.setObjectName("secondaryBtn")
        self._fix_btn.setVisible(False)
        self._fix_btn.clicked.connect(self._install_missing_tools)
        action_row.addWidget(self._fix_btn)

        layout.addLayout(action_row)
        layout.addStretch()

        self._status = QLabel("")
        self._status.setObjectName("viewSubtitle")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._status)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Package File", "",
            "Packages (*.deb *.rpm *.tar.gz *.tar.zst *.tar.xz *.tar.bz2 *.AppImage *.flatpak *.flatpakref);;All Files (*)",
        )
        if path:
            self._handle_file(path)

    def _handle_file(self, path: str) -> None:
        self._status.setText("Analyzing file...")
        self._analysis_bar.setVisible(True)
        self._worker = TaskWorker(analyze_file, path)
        self._worker.finished_sig.connect(self._on_analysis)
        self._worker.start()

    def _on_analysis(self, ok: bool, data: object) -> None:
        self._analysis_bar.setVisible(False)
        if not ok or not isinstance(data, FileAnalysis):
            self._status.setText("Failed to analyze file.")
            return
        self._current_analysis = data
        self._show_analysis(data)

    def _show_analysis(self, a: FileAnalysis) -> None:
        self._analysis_group.setVisible(True)
        self._file_label.setText(Path(a.file_path).name)
        self._type_label.setText(a.file_type.value.upper())

        if a.size_bytes > 1024 * 1024:
            size = f"{a.size_bytes / (1024*1024):.1f} MiB"
        elif a.size_bytes > 1024:
            size = f"{a.size_bytes / 1024:.1f} KiB"
        else:
            size = f"{a.size_bytes} B"
        self._size_label.setText(size)

        self._action_label.setText(a.suggested_action)
        self._build_label.setText(a.detected_build_system or "N/A")

        if a.missing_tools:
            self._tools_label.setText(", ".join(a.missing_tools))
            self._tools_label.setStyleSheet("color: #f38ba8;")
            self._fix_btn.setVisible(True)
            self._install_btn.setVisible(False)
        else:
            self._tools_label.setText("All tools available")
            self._tools_label.setStyleSheet("color: #a6e3a1;")
            self._fix_btn.setVisible(False)
            self._install_btn.setVisible(True)

        self._status.setText("Ready to install." if not a.missing_tools else "Missing tools must be installed first.")

    def _install_missing_tools(self) -> None:
        if not self._current_analysis or not self._current_analysis.missing_tools:
            return
        tools = self._current_analysis.missing_tools
        from asm.core import paru_backend
        from asm.core.pacman_backend import install_command, install_paru_command
        # rpmextract is in official repos; use pacman directly (faster, no AUR)
        if tools == ["rpmextract"]:
            cmd = install_command(tools)
            dlg = ProgressDialog(
                "Installing rpmextract",
                cmd, total_steps=10, privileged=True, parent=self,
            )
            dlg.exec()
            if dlg.success:
                self._handle_file(self._current_analysis.file_path)
            return
        # debtap etc. are in AUR; paru/yay handle both repos and AUR
        helper = paru_backend.get_aur_helper()
        if not helper:
            _log.info("AUR helper missing: auto-installing paru from official repos")
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
                _log.warning("Paru auto-install failed")
                QMessageBox.warning(
                    self, "Installation Failed",
                    "Could not install paru. Some tools (e.g. debtap) require an AUR helper.\n\n"
                    "Try manually: sudo pacman -S paru",
                )
                return
            helper = paru_backend.get_aur_helper()
        if helper:
            _log.info("Installing tools via %s: %s", helper, tools)
            cmd = paru_backend.install_command_for_helper(helper, tools)
            dlg = ProgressDialog(
                f"Installing tools: {', '.join(tools)}",
                cmd, total_steps=20, privileged=False, parent=self,
            )
            dlg.exec()
            if dlg.success:
                self._handle_file(self._current_analysis.file_path)
        else:
            cmd = install_command(tools)
            dlg = ProgressDialog(
                f"Installing tools: {', '.join(tools)}",
                cmd, total_steps=20, privileged=True, parent=self,
            )
            dlg.exec()
            if dlg.success:
                self._handle_file(self._current_analysis.file_path)

    def _do_install(self) -> None:
        a = self._current_analysis
        if not a:
            return

        ft = a.file_type
        if ft == FileType.APPIMAGE:
            self._install_appimage(a.file_path)
        elif ft == FileType.DEB:
            self._install_deb(a.file_path)
        elif ft == FileType.RPM:
            self._install_rpm(a.file_path)
        elif ft == FileType.FLATPAK:
            self._install_flatpak(a.file_path)
        elif ft in (FileType.TAR_GZ, FileType.TAR_ZST):
            self._install_tar(a.file_path, a.detected_build_system)
        else:
            QMessageBox.warning(self, "Unsupported", "This file type is not supported.")

    def _install_appimage(self, path: str) -> None:
        reply = QMessageBox.question(
            self, "Install AppImage",
            "Install this AppImage to ~/Applications and create a desktop entry?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        integrate = reply == QMessageBox.StandardButton.Yes
        self._status.setText("Installing AppImage...")
        worker = TaskWorker(install_appimage, path, integrate)
        worker.finished_sig.connect(self._on_simple_result)
        self._simple_worker = worker
        worker.start()

    def _install_deb(self, path: str) -> None:
        self._last_install_type = FileType.DEB
        self._status.setText("Converting and installing .deb...")
        dlg = DebProgressDialog(path, parent=self)
        dlg.exec()
        if dlg.success:
            invalidate_pacman_cache()
            res = dlg.result
            msg = res.message if hasattr(res, "message") else "Package installed successfully from .deb"
            if hasattr(res, "warnings") and res.warnings:
                msg += "\n\nWarnings:\n" + "\n".join(res.warnings)
            self._status.setText(msg)
            QMessageBox.information(self, "Success", msg)
        else:
            res = dlg.result
            msg = res.message if hasattr(res, "message") else str(res) if res else "Installation failed"
            self._status.setText(msg)
            QMessageBox.warning(self, "Installation Failed", msg)

    def _install_rpm(self, path: str) -> None:
        self._last_install_type = FileType.RPM
        self._status.setText("Extracting and installing .rpm...")
        worker = TaskWorker(install_rpm, path)
        worker.finished_sig.connect(self._on_simple_result)
        self._simple_worker = worker
        worker.start()

    def _install_flatpak(self, path: str) -> None:
        self._last_install_type = FileType.FLATPAK
        self._status.setText("Installing Flatpak...")
        worker = TaskWorker(install_flatpak_file, path)
        worker.finished_sig.connect(self._on_simple_result)
        self._simple_worker = worker
        worker.start()

    def _install_tar(self, path: str, build_system: str) -> None:
        from asm.core.file_installer import install_tar
        cmds = install_tar(path, build_system)
        full_cmd = " && ".join(cmds)
        cmd = ["bash", "-c", full_cmd]
        dlg = ProgressDialog(
            f"Building from source ({build_system or 'manual'})",
            cmd, total_steps=100, privileged=False, parent=self,
        )
        dlg.exec()
        if dlg.success and build_system == "pkgbuild":
            invalidate_pacman_cache()
        self._status.setText("Done" if dlg.success else "Build failed — check log for details")

    def _on_simple_result(self, ok: bool, data: object) -> None:
        from asm.core.file_installer import InstallResult
        if isinstance(data, InstallResult):
            if data.success:
                if getattr(self, "_last_install_type", None) == FileType.DEB:
                    invalidate_pacman_cache()
                elif getattr(self, "_last_install_type", None) == FileType.FLATPAK:
                    flatpak_backend.invalidate_flatpak_cache()
                msg = data.message
                if data.warnings:
                    msg += "\n\nWarnings:\n" + "\n".join(data.warnings)
                QMessageBox.information(self, "Success", msg)
                self._status.setText(data.message)
            else:
                QMessageBox.warning(self, "Installation Failed", data.message)
                self._status.setText(data.message)
        elif isinstance(data, Exception):
            QMessageBox.critical(self, "Error", str(data))
            self._status.setText(str(data))

    # ── Drag & Drop ──
    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        pass

    def dropEvent(self, event) -> None:
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self._handle_file(url.toLocalFile())
                break
