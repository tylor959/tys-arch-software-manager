"""Search bar widget with sort/filter dropdown."""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal, Qt, QTimer
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLineEdit, QComboBox


class SearchBar(QWidget):
    """Search input with debounced signal and sort dropdown."""

    search_changed = pyqtSignal(str)
    sort_changed = pyqtSignal(str)

    def __init__(
        self,
        placeholder: str = "Search...",
        sort_options: list[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchBar")
        self.search_input.setPlaceholderText(placeholder)
        layout.addWidget(self.search_input, 1)

        self.sort_combo = QComboBox()
        if sort_options:
            self.sort_combo.addItems(sort_options)
        layout.addWidget(self.sort_combo)

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(lambda: self.search_changed.emit(self.search_input.text()))

        self.search_input.textChanged.connect(lambda _: self._debounce.start())
        self.sort_combo.currentTextChanged.connect(self.sort_changed.emit)

    def text(self) -> str:
        return self.search_input.text()

    def sort_value(self) -> str:
        return self.sort_combo.currentText()
