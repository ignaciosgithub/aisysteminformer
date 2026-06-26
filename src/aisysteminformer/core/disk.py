"""Disk partition usage and real-time disk I/O rates."""

from __future__ import annotations

import time
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class PartitionUsage:
    """Capacity and usage for a mounted partition (bytes)."""

    device: str
    mountpoint: str
    fstype: str
    total: int
    used: int
    free: int
    percent: float


@dataclass(frozen=True)
class DiskRate:
    """Read/write throughput for a physical disk since the last sample."""

    name: str
    read_bytes_per_sec: float
    write_bytes_per_sec: float
    read_bytes_total: int
    write_bytes_total: int


def list_partitions(*, all_partitions: bool = False) -> list[PartitionUsage]:
    """Return usage for mounted partitions.

    Partitions whose usage cannot be read (e.g. an empty optical drive) are
    skipped rather than raising.
    """

    result: list[PartitionUsage] = []
    for part in psutil.disk_partitions(all=all_partitions):
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue
        result.append(
            PartitionUsage(
                device=part.device,
                mountpoint=part.mountpoint,
                fstype=part.fstype,
                total=usage.total,
                used=usage.used,
                free=usage.free,
                percent=float(usage.percent),
            )
        )
    return result


class DiskRateMonitor:
    """Compute per-disk read/write throughput between successive polls."""

    def __init__(self) -> None:
        self._last_counters: dict[str, psutil._ntuples.sdiskio] = {}
        self._last_time: float | None = None

    def poll(self) -> list[DiskRate]:
        """Return throughput for each physical disk since the previous poll."""

        now = time.monotonic()
        try:
            counters = psutil.disk_io_counters(perdisk=True)
        except (RuntimeError, NotImplementedError):
            counters = {}
        counters = counters or {}
        elapsed = (now - self._last_time) if self._last_time is not None else 0.0
        rates: list[DiskRate] = []
        for name, current in counters.items():
            previous = self._last_counters.get(name)
            if previous is not None and elapsed > 0:
                read_rate = max(0.0, (current.read_bytes - previous.read_bytes) / elapsed)
                write_rate = max(0.0, (current.write_bytes - previous.write_bytes) / elapsed)
            else:
                read_rate = write_rate = 0.0
            rates.append(
                DiskRate(
                    name=name,
                    read_bytes_per_sec=read_rate,
                    write_bytes_per_sec=write_rate,
                    read_bytes_total=current.read_bytes,
                    write_bytes_total=current.write_bytes,
                )
            )
        self._last_counters = counters
        self._last_time = now
        rates.sort(key=lambda r: r.name)
        return rates
