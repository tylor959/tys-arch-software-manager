"""QThread-based async workers with progress, ETA, and log streaming."""

from __future__ import annotations

import time
import subprocess
from typing import Callable, Sequence

from PyQt6.QtCore import QThread, pyqtSignal


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

    def run(self) -> None:
        from asm.core.privilege import run_privileged_stream
        from asm.core.eta_tracker import record_completion

        try:
            if self.privileged:
                proc = run_privileged_stream(self.cmd)
            else:
                proc = subprocess.Popen(
                    self.cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                )

            self.status.emit(f"Running: {' '.join(self.cmd[:3])}...")
            lines_seen = 0
            start = time.monotonic()

            for line in iter(proc.stdout.readline, ""):
                if self._cancelled:
                    proc.kill()
                    self.finished_sig.emit(False, "Cancelled by user")
                    return

                stripped = line.rstrip("\n")
                self.log_line.emit(stripped)
                lines_seen += 1

                pct = min(int((lines_seen / max(self.total_steps, 1)) * 100), 99)
                self.progress.emit(pct)

                elapsed = time.monotonic() - start
                remaining = self._estimate_remaining(elapsed, pct, lines_seen)
                if remaining is not None:
                    mins, secs = divmod(int(remaining), 60)
                    self.eta.emit(f"{mins}m {secs}s remaining")

            proc.wait()
            duration = time.monotonic() - start

            record_completion(self.cmd, lines_seen, duration)

            if proc.returncode == 0:
                self.progress.emit(100)
                self.eta.emit("")
                self.finished_sig.emit(True, "Completed successfully")
            else:
                self.finished_sig.emit(False, f"Exited with code {proc.returncode}")
        except FileNotFoundError:
            self.finished_sig.emit(False, f"Command not found: {self.cmd[0]}")
        except Exception as e:
            self.finished_sig.emit(False, str(e))

    def _estimate_remaining(
        self, elapsed: float, pct: int, lines_seen: int,
    ) -> float | None:
        """Blend duration-based and line-based estimates for better accuracy."""
        estimates: list[float] = []

        if self._predicted_duration and elapsed > 0.5:
            dur_remaining = max(self._predicted_duration - elapsed, 0)
            estimates.append(dur_remaining)

        if pct > 2:
            line_remaining = (elapsed / pct) * (100 - pct)
            estimates.append(line_remaining)

        if not estimates:
            return None
        return sum(estimates) / len(estimates)


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
