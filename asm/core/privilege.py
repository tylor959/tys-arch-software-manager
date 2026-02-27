"""Polkit/pkexec privilege escalation helper."""

import os
import shlex
import shutil
import subprocess
from typing import Sequence


def has_pkexec() -> bool:
    return shutil.which("pkexec") is not None


def run_as_user_stream(
    cmd: Sequence[str],
    timeout: int | None = 600,
) -> subprocess.Popen:
    """Run a command as the current user via pkexec, showing a GUI password dialog.

    Use for AUR helpers (paru, yay) when launched from GUI without a terminal:
    pkexec shows the polkit dialog so the user can authenticate.
    """
    user = os.environ.get("USER", "root")
    full_cmd = ["pkexec", "--user", user, "--"] + list(cmd)
    return subprocess.Popen(
        full_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def run_in_terminal(cmd: Sequence[str]) -> subprocess.Popen | None:
    """Run a command in a visible terminal so the user sees sudo prompts.

    Returns Popen if a terminal was launched, None if no terminal found.
    """
    term_candidates = [
        ("gnome-terminal", ["--", "bash", "-c"]),
        ("konsole", ["-e", "bash", "-c"]),
        ("xfce4-terminal", ["-e", "bash", "-c"]),
        ("xterm", ["-e", "bash", "-c"]),
    ]
    cmd_str = shlex.join(cmd)
    shell_cmd = f"{cmd_str}; echo; read -p 'Press Enter to close'"
    for term, prefix in term_candidates:
        if shutil.which(term):
            full = [term] + prefix + [shell_cmd]
            return subprocess.Popen(full)
    return None


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
