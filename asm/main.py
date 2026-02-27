"""Entry point for Ty's ASM - Arch Software Manager."""

import os
import sys

os.environ.setdefault(
    "QT_LOGGING_RULES",
    "qt.svg.warning=false;qt.qpa.services.warning=false;kf.kio.widgets.kdirmodel=false",
)

from asm.core.logger import setup_logging

setup_logging()

from asm.app import ASMApp
from asm.ui.main_window import MainWindow


def main() -> None:
    app = ASMApp(sys.argv)

    if not app.acquire_lock():
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.warning(None, "Ty's ASM", "Ty's ASM is already running.")
        sys.exit(1)

    window = MainWindow(app)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
