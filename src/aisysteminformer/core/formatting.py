"""Pure formatting helpers shared by the CLI and TUI.

These functions never touch the system; they only turn raw numbers into
human-friendly strings. Keeping them isolated makes them trivial to unit test.
"""

from __future__ import annotations

import datetime as _dt

_BINARY_UNITS = ("B", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB")


def human_bytes(num_bytes: float, *, precision: int = 1) -> str:
    """Format a byte count using binary (IEC) units, e.g. ``1536`` -> ``1.5 KiB``.

    Negative values are formatted with a leading minus sign rather than raising,
    so callers can pass deltas without special-casing.
    """

    if num_bytes != num_bytes:  # NaN guard
        return "n/a"
    sign = "-" if num_bytes < 0 else ""
    value = float(abs(num_bytes))
    for unit in _BINARY_UNITS:
        if value < 1024.0 or unit == _BINARY_UNITS[-1]:
            if unit == "B":
                return f"{sign}{int(value)} {unit}"
            return f"{sign}{value:.{precision}f} {unit}"
        value /= 1024.0
    # Unreachable, but keeps type checkers happy.
    return f"{sign}{value:.{precision}f} {_BINARY_UNITS[-1]}"


def human_rate(bytes_per_second: float, *, precision: int = 1) -> str:
    """Format a throughput value, e.g. ``2048`` -> ``2.0 KiB/s``."""

    return f"{human_bytes(bytes_per_second, precision=precision)}/s"


def human_duration(seconds: float) -> str:
    """Format a duration in seconds as ``[Dd ]HH:MM:SS``."""

    if seconds < 0 or seconds != seconds:
        return "n/a"
    total = int(seconds)
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, secs = divmod(rem, 60)
    if days:
        return f"{days}d {hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def human_percent(value: float, *, precision: int = 1) -> str:
    """Format a 0-100 percentage value."""

    if value != value:
        return "n/a"
    return f"{value:.{precision}f}%"


def format_timestamp(epoch_seconds: float) -> str:
    """Format an epoch timestamp as a local ``YYYY-MM-DD HH:MM:SS`` string."""

    if epoch_seconds <= 0 or epoch_seconds != epoch_seconds:
        return "n/a"
    return _dt.datetime.fromtimestamp(epoch_seconds).strftime("%Y-%m-%d %H:%M:%S")


def truncate(text: str, max_length: int, *, ellipsis: str = "\u2026") -> str:
    """Truncate ``text`` to ``max_length`` characters, appending an ellipsis."""

    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= len(ellipsis):
        return text[:max_length]
    return text[: max_length - len(ellipsis)] + ellipsis
