"""Reusable app card widget — icon, name, description, size, and action buttons."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QSizePolicy,
)


class AppCard(QFrame):
    """Card displaying app info with action buttons.

    Signals:
        install_clicked(str)  - package name
        remove_clicked(str)   - package name
        shortcut_clicked(str) - package name
        info_clicked(str)     - package name
    """

    install_clicked = pyqtSignal(str)
    remove_clicked = pyqtSignal(str)
    shortcut_clicked = pyqtSignal(str)
    info_clicked = pyqtSignal(str)

    def __init__(
        self,
        name: str,
        description: str = "",
        size: str = "",
        icon: QIcon | None = None,
        installed: bool = False,
        votes: int | None = None,
        popularity: float | None = None,
        version: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.pkg_name = name
        self.setObjectName("appCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(120)

        root = QHBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 8)
        root.setSpacing(12)

        # Icon
        self._icon_label = QLabel()
        self._icon_label.setFixedSize(48, 48)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if icon and not icon.isNull():
            pixmap = icon.pixmap(QSize(48, 48))
            self._icon_label.setPixmap(pixmap)
        else:
            self._icon_label.setText("?")
            self._icon_label.setStyleSheet(
                "background: #45475a; border-radius: 10px; color: #cdd6f4; font-size: 20px; font-weight: bold;"
            )
        root.addWidget(self._icon_label)

        # Info column
        info_col = QVBoxLayout()
        info_col.setSpacing(2)

        name_row = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setObjectName("appName")
        name_row.addWidget(name_label)

        if version:
            ver_label = QLabel(version)
            ver_label.setObjectName("appSize")
            name_row.addWidget(ver_label)

        name_row.addStretch()
        info_col.addLayout(name_row)

        if description:
            desc = QLabel(description)
            desc.setObjectName("appDesc")
            desc.setWordWrap(True)
            desc.setMaximumHeight(32)
            info_col.addWidget(desc)

        meta_row = QHBoxLayout()
        meta_row.setSpacing(12)
        if size:
            size_l = QLabel(size)
            size_l.setObjectName("appSize")
            meta_row.addWidget(size_l)
        if votes is not None:
            votes_l = QLabel(f"\u2605 {votes}")
            votes_l.setObjectName("appVotes")
            meta_row.addWidget(votes_l)
        if popularity is not None:
            pop_l = QLabel(f"Pop: {popularity:.2f}")
            pop_l.setObjectName("appSize")
            meta_row.addWidget(pop_l)
        meta_row.addStretch()
        info_col.addLayout(meta_row)

        root.addLayout(info_col, 1)

        # Action buttons
        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)
        btn_col.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        compact = "padding: 4px 12px; font-size: 12px;"

        if installed:
            remove_btn = QPushButton("Remove")
            remove_btn.setObjectName("dangerBtn")
            remove_btn.setFixedSize(82, 28)
            remove_btn.setStyleSheet(f"QPushButton {{ {compact} }}")
            remove_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            remove_btn.clicked.connect(lambda: self.remove_clicked.emit(self.pkg_name))
            btn_col.addWidget(remove_btn)

            shortcut_btn = QPushButton("Shortcut")
            shortcut_btn.setObjectName("secondaryBtn")
            shortcut_btn.setFixedSize(82, 28)
            shortcut_btn.setStyleSheet(f"QPushButton {{ {compact} }}")
            shortcut_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            shortcut_btn.clicked.connect(lambda: self.shortcut_clicked.emit(self.pkg_name))
            btn_col.addWidget(shortcut_btn)

            info_btn = QPushButton("Files")
            info_btn.setObjectName("secondaryBtn")
            info_btn.setFixedSize(82, 28)
            info_btn.setStyleSheet(f"QPushButton {{ {compact} }}")
            info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            info_btn.clicked.connect(lambda: self.info_clicked.emit(self.pkg_name))
            btn_col.addWidget(info_btn)
        else:
            install_btn = QPushButton("Install")
            install_btn.setObjectName("primaryBtn")
            install_btn.setFixedSize(82, 28)
            install_btn.setStyleSheet(f"QPushButton {{ {compact} }}")
            install_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            install_btn.clicked.connect(lambda: self.install_clicked.emit(self.pkg_name))
            btn_col.addWidget(install_btn)

        root.addLayout(btn_col)

    def set_icon(self, icon: QIcon) -> None:
        if icon and not icon.isNull():
            self._icon_label.setPixmap(icon.pixmap(QSize(48, 48)))
            self._icon_label.setStyleSheet("")
