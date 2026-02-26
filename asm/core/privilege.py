"""Polkit/pkexec privilege escalation helper."""

import subprocess
import shutil
from typing import Sequence


def has_pkexec() -> bool:
    return shutil.which("pkexec") is not None


def run_privileged(
    cmd: Sequence[str],
    capture: bool = True,
    timeout: int | None = 300,
) -> subprocess.CompletedProcess:
    """Run a command with pkexec for privilege escalation.

    Falls back to direct execution if pkexec is unavailable (useful for testing
    when already running as root).
    """
    full_cmd = ["pkexec"] + list(cmd) if has_pkexec() else list(cmd)
    return subprocess.run(
        full_cmd,
        capture_output=capture,
        text=True,
        timeout=timeout,
    )


def run_privileged_stream(
    cmd: Sequence[str],
    timeout: int | None = 600,
) -> subprocess.Popen:
    """Start a privileged command and return the Popen for streaming output."""
    full_cmd = ["pkexec"] + list(cmd) if has_pkexec() else list(cmd)
    return subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
