"""Settings view — app configuration, repo manager, disk tools, diagnostics toolbox."""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTabWidget, QFormLayout,
    QComboBox, QCheckBox, QPushButton, QGroupBox,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QLineEdit,
)

from asm.core.config import Config
from asm.ui.widgets.diagnostics_dialog import DiagnosticsDialog
from asm.ui.widgets.progress_dialog import ProgressDialog


# Mount points that should NEVER be offered as install targets.
# Based on the Filesystem Hierarchy Standard (FHS):
#   /boot, /efi          - Bootloader and kernel — corruption = unbootable system
#   /proc, /sys, /dev    - Virtual kernel filesystems, not real storage
#   /run                 - Volatile runtime data (tmpfs), cleared on reboot
#   /tmp, /var/tmp       - Temporary files, world-writable, often tmpfs
#   /var, /var/*          - Variable system data (logs, caches, databases)
#   /srv                 - Site-specific service data (web servers, FTP, etc.)
#   /snap                - Snap package mounts
UNSAFE_MOUNTS = frozenset({
    "/boot", "/boot/efi", "/efi",
    "/proc", "/sys", "/dev", "/run",
    "/tmp", "/var/tmp",
    "/var", "/var/log", "/var/cache", "/var/lib",
    "/srv",
    "/snap",
})

UNSAFE_PREFIXES = (
    "/proc/", "/sys/", "/dev/", "/run/",
    "/snap/", "/var/", "/srv/",
)


def _is_safe_mount(mount: str) -> bool:
    """Return True if a mount point is safe for storing applications."""
    if mount in UNSAFE_MOUNTS:
        return False
    for prefix in UNSAFE_PREFIXES:
        if mount.startswith(prefix):
            return False
    return True


def _get_mount_info() -> list[dict]:
    """Get mount points with size, free space, and filesystem type.

    Uses `findmnt` which correctly reports btrfs subvolumes and all real
    mount points, unlike lsblk which only shows block device partitions.
    """
    mounts: list[dict] = []
    seen: set[str] = set()
    try:
        result = subprocess.run(
            ["findmnt", "-rno", "TARGET,SIZE,AVAIL,FSTYPE,SOURCE"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split(None, 4)
            if not parts or not parts[0].startswith("/"):
                continue
            mount = parts[0]
            if mount in seen:
                continue
            seen.add(mount)

            size = parts[1] if len(parts) > 1 else "?"
            avail = parts[2] if len(parts) > 2 else "?"
            fstype = parts[3] if len(parts) > 3 else "?"
            device = parts[4] if len(parts) > 4 else "?"

            # Skip virtual/pseudo filesystems and zero-size mounts
            if fstype in ("tmpfs", "devtmpfs", "devpts", "efivarfs",
                          "sysfs", "proc", "cgroup2", "securityfs",
                          "pstore", "bpf", "tracefs", "debugfs",
                          "configfs", "fusectl", "ramfs", "hugetlbfs",
                          "mqueue", "autofs", "overlay") \
                    or fstype.startswith("fuse.") \
                    or size == "0" or size == "0B":
                continue

            safe = _is_safe_mount(mount)

            free_str = avail
            try:
                stat = os.statvfs(mount)
                free_bytes = stat.f_bavail * stat.f_frsize
                free_gb = free_bytes / (1024**3)
                free_str = f"{free_gb:.1f}G free"
            except OSError:
                pass

            mounts.append({
                "mount": mount,
                "size": size,
                "free": free_str,
                "fstype": fstype,
                "device": device,
                "safe": safe,
            })
    except Exception:
        mounts.append({"mount": "/", "size": "?", "free": "?", "fstype": "?", "device": "?", "safe": True})
    return mounts


class SettingsView(QWidget):
    """Global settings panel with tabs for preferences, repos, disks, and diagnostics."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = Config()
        self._build_ui()
        self._load_settings()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 12)
        layout.setSpacing(12)

        title = QLabel("Settings")
        title.setObjectName("viewTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_general_tab(), "General")
        tabs.addTab(self._build_disk_tab(), "Disk Setup")
        tabs.addTab(self._build_repos_tab(), "Repositories")
        tabs.addTab(self._build_diagnostics_tab(), "Diagnostics")
        tabs.addTab(self._build_about_tab(), "About")
        layout.addWidget(tabs, 1)

    # ── General Tab ──
    def _build_general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(16)
        form.setContentsMargins(16, 16, 16, 16)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        form.addRow("Theme:", self.theme_combo)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["a-z", "z-a", "size", "votes", "popularity"])
        self.sort_combo.currentTextChanged.connect(
            lambda v: self.config.set("default_sort", v)
        )
        form.addRow("Default sort:", self.sort_combo)

        self.auto_shortcut = QCheckBox("Automatically add desktop shortcut on install")
        self.auto_shortcut.toggled.connect(
            lambda v: self.config.set("auto_desktop_shortcut", v)
        )
        form.addRow(self.auto_shortcut)

        self.show_all_default = QCheckBox("Show all packages by default (not just apps)")
        self.show_all_default.toggled.connect(
            lambda v: self.config.set("show_all_packages", v)
        )
        form.addRow(self.show_all_default)

        # Disk selector with safety filtering
        self.disk_combo = QComboBox()
        self._populate_safe_disks()
        self.disk_combo.currentIndexChanged.connect(self._on_disk_changed)
        form.addRow("Default install disk:", self.disk_combo)

        self._disk_warning = QLabel("")
        self._disk_warning.setWordWrap(True)
        self._disk_warning.setObjectName("appSize")
        self._disk_warning.setVisible(False)
        form.addRow(self._disk_warning)

        form.addRow(QLabel(""))
        reset_btn = QPushButton("Reset All Settings")
        reset_btn.setObjectName("dangerBtn")
        reset_btn.clicked.connect(self._reset_settings)
        form.addRow(reset_btn)

        return page

    # ── Disk Setup Tab ──
    def _build_disk_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        info = QLabel(
            "Pick a disk to store your applications on, then click Auto-Configure.\n"
            "This creates an Applications folder, sets permissions, and makes it your default."
        )
        info.setObjectName("viewSubtitle")
        info.setWordWrap(True)
        layout.addWidget(info)

        # Disk list (only safe disks)
        self._disk_list = QListWidget()
        self._disk_list.setObjectName("categoryList")
        self._disk_list.setAlternatingRowColors(True)
        self._disk_list.currentRowChanged.connect(self._on_disk_list_changed)
        layout.addWidget(self._disk_list, 1)

        self._disk_detail = QLabel("")
        self._disk_detail.setObjectName("appSize")
        self._disk_detail.setWordWrap(True)
        layout.addWidget(self._disk_detail)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        self._auto_configure_btn = QPushButton("Auto-Configure Selected Disk")
        self._auto_configure_btn.setObjectName("primaryBtn")
        self._auto_configure_btn.setToolTip(
            "Creates an Applications folder, fixes permissions, and sets this disk as your default"
        )
        self._auto_configure_btn.clicked.connect(self._auto_configure_disk)
        btn_row.addWidget(self._auto_configure_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._refresh_disk_list)
        btn_row.addWidget(refresh_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._disk_status = QLabel("")
        self._disk_status.setObjectName("appSize")
        self._disk_status.setWordWrap(True)
        layout.addWidget(self._disk_status)

        self._refresh_disk_list()
        return page

    # ── Repos Tab ──
    def _build_repos_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel("Manage pacman repositories from /etc/pacman.conf")
        info.setObjectName("viewSubtitle")
        layout.addWidget(info)

        self._repo_list = QListWidget()
        self._repo_list.setObjectName("categoryList")
        layout.addWidget(self._repo_list, 1)

        btn_row = QHBoxLayout()
        refresh_btn = QPushButton("Refresh")
        refresh_btn.setObjectName("secondaryBtn")
        refresh_btn.clicked.connect(self._load_repos)
        btn_row.addWidget(refresh_btn)

        add_btn = QPushButton("Add Repository")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_repo)
        btn_row.addWidget(add_btn)

        toggle_btn = QPushButton("Toggle Selected")
        toggle_btn.setObjectName("secondaryBtn")
        toggle_btn.clicked.connect(self._toggle_repo)
        btn_row.addWidget(toggle_btn)

        sync_btn = QPushButton("Sync Databases")
        sync_btn.setObjectName("primaryBtn")
        sync_btn.clicked.connect(self._sync_databases)
        btn_row.addWidget(sync_btn)

        layout.addLayout(btn_row)

        self._load_repos()
        return page

    # ── Diagnostics Tab ──
    def _build_diagnostics_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel("System health checks and repair tools")
        info.setObjectName("viewSubtitle")
        layout.addWidget(info)

        run_btn = QPushButton("Run Full Diagnostics")
        run_btn.setObjectName("primaryBtn")
        run_btn.clicked.connect(self._open_diagnostics)
        layout.addWidget(run_btn)

        group = QGroupBox("Quick Actions")
        quick_layout = QVBoxLayout(group)
        quick_layout.setSpacing(8)

        actions = [
            ("Refresh pacman keyring", ["pacman-key", "--init"]),
            ("Populate keyring", ["pacman-key", "--populate", "archlinux"]),
            ("Clean package cache (keep 1 version)", ["paccache", "-rk1"]),
            ("Remove all orphaned packages", None),
            ("Update mirror list (reflector)", ["reflector", "--latest", "10", "--sort", "rate", "--save", "/etc/pacman.d/mirrorlist"]),
            ("Force sync all databases", ["pacman", "-Syy"]),
        ]

        for label, cmd in actions:
            btn = QPushButton(label)
            btn.setObjectName("secondaryBtn")
            if cmd:
                btn.clicked.connect(lambda checked, c=cmd, l=label: self._run_quick_action(c, l))
            else:
                btn.clicked.connect(self._remove_orphans)
            quick_layout.addWidget(btn)

        layout.addWidget(group)
        layout.addStretch()
        return page

    # ── About Tab ──
    def _build_about_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        name = QLabel("Ty's ASM")
        name.setObjectName("viewTitle")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name)

        version = QLabel("Arch Software Manager v1.0.0")
        version.setObjectName("viewSubtitle")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "A friendly software center for Arch Linux.\n"
            "Designed for new users who want a simple way to\n"
            "install, remove, and manage their software."
        )
        desc.setObjectName("viewSubtitle")
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        layout.addSpacing(20)

        license_label = QLabel("License: GPLv3")
        license_label.setObjectName("appSize")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)

        return page

    # ────────────────────────────────────
    # Logic: General
    # ────────────────────────────────────

    def _load_settings(self) -> None:
        self.theme_combo.setCurrentText(self.config.get("theme"))
        self.sort_combo.setCurrentText(self.config.get("default_sort"))
        self.auto_shortcut.setChecked(self.config.get("auto_desktop_shortcut"))
        self.show_all_default.setChecked(self.config.get("show_all_packages"))

    def _on_theme_changed(self, theme: str) -> None:
        self.config.set("theme", theme)
        main_window = self.window()
        if hasattr(main_window, "app"):
            main_window.app.apply_theme(theme)

    def _populate_safe_disks(self) -> None:
        """Populate disk selector with only safe mount points."""
        mounts = _get_mount_info()
        current = self.config.get("default_install_disk")
        select_idx = 0
        for m in mounts:
            if not m["safe"]:
                continue
            label = f"{m['mount']}  ({m['size']}, {m['free']}, {m['fstype']})"
            self.disk_combo.addItem(label, m["mount"])
            if m["mount"] == current:
                select_idx = self.disk_combo.count() - 1
        if self.disk_combo.count() > 0:
            self.disk_combo.setCurrentIndex(select_idx)

    def _on_disk_changed(self, index: int) -> None:
        mount = self.disk_combo.itemData(index)
        if not mount:
            return
        self.config.set("default_install_disk", mount)

        # Show a contextual note for root
        if mount == "/":
            self._disk_warning.setText(
                "Using root partition. This is fine for most users. "
                "If you have a separate data disk, consider selecting it instead."
            )
            self._disk_warning.setVisible(True)
        else:
            self._disk_warning.setVisible(False)

    def _reset_settings(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Settings",
            "Reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.config.reset()
            self._load_settings()

    # ────────────────────────────────────
    # Logic: Disk Setup
    # ────────────────────────────────────

    def _refresh_disk_list(self) -> None:
        self._disk_list.clear()
        self._safe_mounts: list[dict] = []
        current_default = self.config.get("default_install_disk")

        mounts = _get_mount_info()
        select_row = 0
        for m in mounts:
            if not m["safe"]:
                continue
            self._safe_mounts.append(m)

            app_dir = os.path.join(m["mount"], "Applications")
            configured = os.path.isdir(app_dir)
            is_default = m["mount"] == current_default

            tag_parts: list[str] = []
            if is_default:
                tag_parts.append("DEFAULT")
            if configured:
                tag_parts.append("ready")
            tag = f"  [{', '.join(tag_parts)}]" if tag_parts else ""

            label = f"{m['mount']}  —  {m['size']},  {m['free']}{tag}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, m)
            self._disk_list.addItem(item)

            if m["mount"] == current_default:
                select_row = self._disk_list.count() - 1

        if self._disk_list.count() > 0:
            self._disk_list.setCurrentRow(select_row)

    def _on_disk_list_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._safe_mounts):
            self._disk_detail.setText("")
            return
        m = self._safe_mounts[row]
        app_dir = os.path.join(m["mount"], "Applications")
        configured = os.path.isdir(app_dir)
        writable = os.access(app_dir, os.W_OK) if configured else False

        lines = [
            f"Mount: {m['mount']}    Device: {m['device']}    FS: {m['fstype']}",
            f"Size: {m['size']}    Free: {m['free']}",
        ]
        if configured:
            lines.append(f"Applications folder: {app_dir}  ({'writable' if writable else 'NOT writable — will be fixed'})")
        else:
            lines.append("No Applications folder yet — Auto-Configure will create one.")

        if m["mount"] == "/":
            lines.append("Tip: This is your root partition. If you have a separate data disk, it may be a better choice.")

        self._disk_detail.setText("\n".join(lines))

    def _auto_configure_disk(self) -> None:
        item = self._disk_list.currentItem()
        if not item:
            QMessageBox.information(self, "No Selection", "Select a disk from the list first.")
            return
        m = item.data(Qt.ItemDataRole.UserRole)
        mount = m["mount"]
        app_dir = os.path.join(mount, "Applications")

        reply = QMessageBox.question(
            self, "Auto-Configure Disk",
            f"This will:\n\n"
            f"  1. Create  {app_dir}\n"
            f"  2. Set ownership to your user ({os.getlogin()})\n"
            f"  3. Make this your default install location\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        user = os.getlogin()
        script = (
            f"mkdir -p '{app_dir}' && "
            f"chown -R {user}:{user} '{app_dir}' && "
            f"chmod -R u+rwX,go+rX '{app_dir}'"
        )
        cmd = ["bash", "-c", script]
        dlg = ProgressDialog("Configuring disk", cmd, total_steps=5, privileged=True, parent=self)
        dlg.exec()

        if dlg.success:
            self.config.set("default_install_disk", mount)
            for i in range(self.disk_combo.count()):
                if self.disk_combo.itemData(i) == mount:
                    self.disk_combo.setCurrentIndex(i)
                    break
            self._disk_status.setText(f"Done — {app_dir} is ready and set as default.")
            self._refresh_disk_list()
        else:
            self._disk_status.setText("Configuration failed. Check the log for details.")

    # ────────────────────────────────────
    # Logic: Repositories
    # ────────────────────────────────────

    def _load_repos(self) -> None:
        self._repo_list.clear()
        conf = Path("/etc/pacman.conf")
        if not conf.exists():
            return
        try:
            text = conf.read_text()
            for match in re.finditer(r"^(\#?\[)(\w[\w-]*)\]", text, re.MULTILINE):
                prefix = match.group(1)
                name = match.group(2)
                if name == "options":
                    continue
                enabled = not prefix.startswith("#")
                item = QListWidgetItem(f"{'[active]' if enabled else '[disabled]'}  {name}")
                item.setData(Qt.ItemDataRole.UserRole, name)
                self._repo_list.addItem(item)
        except OSError:
            pass

    def _add_repo(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Repository", "Repository name:")
        if not ok or not name.strip():
            return
        server, ok2 = QInputDialog.getText(
            self, "Add Repository", "Server URL (e.g., https://mirror.example.com/$repo/os/$arch):"
        )
        if not ok2 or not server.strip():
            return

        block = f"\n[{name.strip()}]\nServer = {server.strip()}\n"
        cmd = ["bash", "-c", f"echo '{block}' >> /etc/pacman.conf"]
        dlg = ProgressDialog("Adding repository", cmd, total_steps=5, privileged=True, parent=self)
        dlg.exec()
        self._load_repos()

    def _toggle_repo(self) -> None:
        item = self._repo_list.currentItem()
        if not item:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        text = item.text()
        if "[active]" in text:
            cmd = ["bash", "-c", f"sed -i 's/^\\[{name}\\]/#[{name}]/' /etc/pacman.conf"]
        else:
            cmd = ["bash", "-c", f"sed -i 's/^#\\[{name}\\]/[{name}]/' /etc/pacman.conf"]
        dlg = ProgressDialog(f"Toggling {name}", cmd, total_steps=5, privileged=True, parent=self)
        dlg.exec()
        self._load_repos()

    def _sync_databases(self) -> None:
        dlg = ProgressDialog("Syncing databases", ["pacman", "-Sy"], total_steps=20, privileged=True, parent=self)
        dlg.exec()

    # ────────────────────────────────────
    # Logic: Diagnostics
    # ────────────────────────────────────

    def _open_diagnostics(self) -> None:
        dlg = DiagnosticsDialog(parent=self)
        dlg.exec()

    def _run_quick_action(self, cmd: list[str], label: str) -> None:
        dlg = ProgressDialog(label, cmd, total_steps=20, privileged=True, parent=self)
        dlg.exec()

    def _remove_orphans(self) -> None:
        try:
            result = subprocess.run(
                ["pacman", "-Qdtq"], capture_output=True, text=True, timeout=10,
            )
            orphans = [l.strip() for l in result.stdout.strip().splitlines() if l.strip()]
            if not orphans:
                QMessageBox.information(self, "No Orphans", "No orphaned packages found.")
                return
            reply = QMessageBox.question(
                self, "Remove Orphans",
                f"Remove {len(orphans)} orphaned packages?\n\n{', '.join(orphans[:10])}{'...' if len(orphans) > 10 else ''}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.Yes:
                cmd = ["pacman", "-Rns", "--noconfirm"] + orphans
                dlg = ProgressDialog("Removing orphans", cmd, total_steps=20, privileged=True, parent=self)
                dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))
