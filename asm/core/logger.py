"""Logging setup for Ty's ASM — file handler, excepthook, and log path."""

from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path

from asm.core.config import CACHE_DIR

LOG_FILE = CACHE_DIR / "tys-asm.log"
LOG_MAX_BYTES = 512 * 1024  # 512 KB
LOG_BACKUP_COUNT = 2


def setup_logging() -> None:
    """Configure logging to file and install excepthook for uncaught exceptions."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger("asm")
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers
    if not root.handlers:
        try:
            from logging.handlers import RotatingFileHandler

            handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_MAX_BYTES,
                backupCount=LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
        except OSError:
            handler = logging.StreamHandler(sys.stderr)

        handler.setLevel(logging.DEBUG)
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root.addHandler(handler)

    sys.excepthook = _excepthook


def _excepthook(exc_type: type, exc_value: BaseException, exc_tb) -> None:
    """Log uncaught exceptions to file and stderr."""
    lines = traceback.format_exception(exc_type, exc_value, exc_tb)
    msg = "".join(lines)
    logger = logging.getLogger("asm")
    logger.critical("Uncaught exception:\n%s", msg)
    sys.__excepthook__(exc_type, exc_value, exc_tb)


def get_logger(name: str) -> logging.Logger:
    """Return a logger for the given module name."""
    return logging.getLogger(f"asm.{name}")


def get_log_path() -> Path:
    """Return the path to the log file."""
    return LOG_FILE
