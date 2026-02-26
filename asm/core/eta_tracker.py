"""Self-improving ETA tracker.

Stores historical operation durations and line counts so that future
ETA predictions become more accurate over time.  Data is persisted to
``~/.config/tys-asm/eta_history.json``.

Each operation is keyed by a short identifier derived from the command
(e.g. ``pacman_-S``, ``paru_-S``, ``pacman_-Rns``).  We keep the last
20 observations per key and use their median for predictions.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import Sequence

from asm.core.config import CONFIG_DIR

_HISTORY_FILE = CONFIG_DIR / "eta_history.json"
_MAX_SAMPLES = 20
_DEFAULT_LINES = 50


def _op_key(cmd: Sequence[str]) -> str:
    """Derive a short key from a command list.

    Examples:
        ["pacman", "-S", "--noconfirm", "firefox"]  ->  "pacman_-S"
        ["paru", "-S", "yay"]                        ->  "paru_-S"
    """
    if not cmd:
        return "unknown"
    base = Path(cmd[0]).name
    flag = ""
    for arg in cmd[1:]:
        if arg.startswith("-") and not arg.startswith("--"):
            flag = arg
            break
    return f"{base}_{flag}" if flag else base


def _load() -> dict:
    try:
        if _HISTORY_FILE.exists():
            return json.loads(_HISTORY_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save(data: dict) -> None:
    try:
        _HISTORY_FILE.write_text(json.dumps(data, indent=1))
    except OSError:
        pass


def estimate_total_lines(cmd: Sequence[str]) -> int:
    """Predict how many output lines this command will produce.

    Returns a reasonable default if no history is available.
    """
    key = _op_key(cmd)
    history = _load()
    samples = history.get(key, {}).get("lines", [])
    if samples:
        return max(int(statistics.median(samples)), 5)
    return _DEFAULT_LINES


def record_completion(
    cmd: Sequence[str],
    total_lines: int,
    duration_secs: float,
) -> None:
    """Record a completed operation for future ETA predictions."""
    key = _op_key(cmd)
    history = _load()
    entry = history.setdefault(key, {"lines": [], "durations": []})
    entry["lines"].append(total_lines)
    entry["durations"].append(round(duration_secs, 2))
    entry["lines"] = entry["lines"][-_MAX_SAMPLES:]
    entry["durations"] = entry["durations"][-_MAX_SAMPLES:]
    _save(history)


def estimate_duration(cmd: Sequence[str]) -> float | None:
    """Predict total duration in seconds, or None if no history."""
    key = _op_key(cmd)
    history = _load()
    samples = history.get(key, {}).get("durations", [])
    if samples:
        return statistics.median(samples)
    return None
