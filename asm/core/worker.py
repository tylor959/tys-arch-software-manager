"""QThread-based async workers with progress, ETA, and log streaming."""

from __future__ import annotations

import subprocess
import time
from typing import Callable, Sequence

from PyQt6.QtCore import QThread, pyqtSignal

from asm.core.logger import get_logger

_log = get_logger("worker")


class CommandWorker(QThread):
    """Runs a shell command in a thread, streaming output line by line.

    Uses historical data from ``eta_tracker`` to predict total output
    lines and operation duration.  After each operation completes, the
    actual values are recorded so future predictions improve over time.

    Signals:
        progress(int)       - 0..100 percentage (estimated)
        status(str)         - human-readable status message
        log_line(str)       - single line of stdout/stderr
        eta(str)            - estimated time remaining
        finished_sig(bool, str) - (success, message)
    """

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    log_line = pyqtSignal(str)
    eta = pyqtSignal(str)
    finished_sig = pyqtSignal(bool, str)
    indeterminate_sig = pyqtSignal(bool)

    def __init__(
        self,
        cmd: Sequence[str],
        total_steps: int = 1,
        privileged: bool = False,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.cmd = list(cmd)
        self.privileged = privileged
        self._cancelled = False

        from asm.core.eta_tracker import estimate_total_lines, estimate_duration
        learned = estimate_total_lines(cmd)
        self.total_steps = max(learned, total_steps, 1)
        self._predicted_duration = estimate_duration(cmd)

    def cancel(self) -> None:
        self._cancelled = True

    def _is_aur_helper(self) -> bool:
        """Check if the command is an AUR helper that may need a visible sudo prompt."""
        if not self.cmd:
            return False
        exe = self.cmd[0].lower()
        return "paru" in exe or "yay" in exe

    def run(self) -> None:
        from asm.core.privilege import (
            has_pkexec,
            run_as_user_stream,
            run_in_terminal,
            run_privileged_stream,
        )
        from asm.core.eta_tracker import is_using_bootstrap, record_completion

        _log.info("CommandWorker: starting %s", " ".join(self.cmd[:5]))
        if is_using_bootstrap(self.cmd):
            self.indeterminate_sig.emit(True)
        try:
            if self.privileged:
                proc = run_privileged_stream(self.cmd)
            elif not self._is_aur_helper():
                proc = subprocess.Popen(
                    self.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )
            elif has_pkexec():
                # AUR helper from GUI: use pkexec --user for visible polkit dialog
                proc = run_as_user_stream(self.cmd)
            else:
                # Fallback: run in terminal so user sees sudo prompt
                term_proc = run_in_terminal(self.cmd)
                if term_proc is not None:
                    self.indeterminate_sig.emit(False)
                    self.status.emit("Opened terminal — complete installation there.")
                    term_proc.wait()
                    self.finished_sig.emit(True, "Terminal opened for installation")
                    return
                proc = subprocess.Popen(
                    self.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            self.status.emit(f"Running: {' '.join(self.cmd[:3])}...")
            lines_seen = 0
            start = time.monotonic()
            indeterminate_cleared = False

            for line in iter(proc.stdout.readline, ""):
                if self._cancelled:
                    proc.kill()
                    self.finished_sig.emit(False, "Cancelled by user")
                    return

                stripped = line.rstrip("\n")
                self.log_line.emit(stripped)
                lines_seen += 1

                if not indeterminate_cleared and (lines_seen > 0 or (time.monotonic() - start) >= 3):
                    self.indeterminate_sig.emit(False)
                    indeterminate_cleared = True

                pct = min(int((lines_seen / max(self.total_steps, 1)) * 100), 99)
                self.progress.emit(pct)

                elapsed = time.monotonic() - start
                remaining = self._estimate_remaining(elapsed, pct, lines_seen)
                if remaining is not None:
                    mins, secs = divmod(int(remaining), 60)
                    self.eta.emit(f"{mins}m {secs}s remaining")

            proc.wait()
            duration = time.monotonic() - start

            if not indeterminate_cleared:
                self.indeterminate_sig.emit(False)

            record_completion(self.cmd, lines_seen, duration)

            if proc.returncode == 0:
                self.progress.emit(100)
                self.eta.emit("")
                _log.info("CommandWorker: completed successfully")
                self.finished_sig.emit(True, "Completed successfully")
            else:
                _log.warning("CommandWorker: exited with code %s", proc.returncode)
                self.finished_sig.emit(False, f"Exited with code {proc.returncode}")
        except FileNotFoundError:
            self.indeterminate_sig.emit(False)
            _log.warning("CommandWorker: command not found: %s", self.cmd[0])
            self.finished_sig.emit(False, f"Command not found: {self.cmd[0]}")
        except Exception as e:
            self.indeterminate_sig.emit(False)
            _log.exception("CommandWorker: error")
            self.finished_sig.emit(False, str(e))

    def _estimate_remaining(
        self, elapsed: float, pct: int, lines_seen: int,
    ) -> float | None:
        """Blend duration-based and line-based estimates for better accuracy.

        Weight duration more heavily once we have ~10% progress, since
        duration tends to be more stable than line count for package ops.
        """
        estimates: list[tuple[float, float]] = []  # (value, weight)

        if self._predicted_duration and elapsed > 0.5:
            dur_remaining = max(self._predicted_duration - elapsed, 0)
            # Weight duration 2x when pct >= 10, since it's more reliable
            weight = 2.0 if pct >= 10 else 1.0
            estimates.append((dur_remaining, weight))

        if pct > 2:
            line_remaining = (elapsed / pct) * (100 - pct)
            estimates.append((line_remaining, 1.0))

        if not estimates:
            return None
        total_weight = sum(w for _, w in estimates)
        return sum(v * w for v, w in estimates) / total_weight


class TaskWorker(QThread):
    """Runs an arbitrary Python callable in a background thread."""

    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished_sig = pyqtSignal(bool, object)

    def __init__(self, task: Callable, *args, parent=None, **kwargs) -> None:
        super().__init__(parent)
        self._task = task
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._task(*self._args, **self._kwargs)
            self.finished_sig.emit(True, result)
        except Exception as e:
            self.finished_sig.emit(False, e)


class DebInstallWorker(QThread):
    """Runs install_deb with progress callbacks for step-based feedback."""

    progress_status = pyqtSignal(str)
    finished_sig = pyqtSignal(bool, object)

    def __init__(self, path: str, parent=None) -> None:
        super().__init__(parent)
        self._path = path

    def run(self) -> None:
        from asm.core.file_installer import install_deb

        def on_progress(msg: str) -> None:
            self.progress_status.emit(msg)

        try:
            result = install_deb(self._path, progress_callback=on_progress)
            self.finished_sig.emit(result.success, result)
        except Exception as e:
            self.finished_sig.emit(False, e)
