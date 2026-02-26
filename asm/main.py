"""Entry point for Ty's ASM - Arch Software Manager."""

import os
import sys

os.environ.setdefault("QT_LOGGING_RULES", "qt.qpa.services.warning=false")

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
