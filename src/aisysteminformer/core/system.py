"""System-wide resource statistics: CPU, memory, swap and uptime."""

from __future__ import annotations

import platform
import time
from dataclasses import dataclass, field

import psutil


@dataclass(frozen=True)
class MemoryStats:
    """A snapshot of physical or virtual memory usage (all values in bytes)."""

    total: int
    used: int
    available: int
    percent: float


@dataclass(frozen=True)
class CpuStats:
    """A snapshot of CPU utilisation."""

    percent_overall: float
    percent_per_core: list[float] = field(default_factory=list)
    logical_cores: int = 0
    physical_cores: int = 0
    load_average: tuple[float, float, float] | None = None


@dataclass(frozen=True)
class SystemSnapshot:
    """A single point-in-time snapshot of system-wide statistics."""

    hostname: str
    platform: str
    boot_time: float
    uptime_seconds: float
    cpu: CpuStats
    memory: MemoryStats
    swap: MemoryStats


def cpu_stats(*, per_core: bool = True) -> CpuStats:
    """Return current CPU statistics.

    ``psutil.cpu_percent`` with ``interval=None`` is non-blocking and reports
    usage since the previous call, so callers polling on a timer get meaningful
    values without stalling the UI.
    """

    overall = psutil.cpu_percent(interval=None)
    per_core_values = psutil.cpu_percent(interval=None, percpu=True) if per_core else []
    try:
        load = psutil.getloadavg()
    except (AttributeError, OSError):
        load = None
    return CpuStats(
        percent_overall=float(overall),
        percent_per_core=[float(value) for value in per_core_values],
        logical_cores=psutil.cpu_count(logical=True) or 0,
        physical_cores=psutil.cpu_count(logical=False) or 0,
        load_average=load,
    )


def memory_stats() -> MemoryStats:
    """Return current physical memory statistics."""

    vm = psutil.virtual_memory()
    return MemoryStats(
        total=vm.total,
        used=vm.total - vm.available,
        available=vm.available,
        percent=float(vm.percent),
    )


def swap_stats() -> MemoryStats:
    """Return current swap statistics. ``available`` maps to swap ``free``."""

    sw = psutil.swap_memory()
    return MemoryStats(
        total=sw.total,
        used=sw.used,
        available=sw.free,
        percent=float(sw.percent),
    )


def snapshot(*, per_core: bool = True) -> SystemSnapshot:
    """Collect a full system snapshot in one call."""

    boot = psutil.boot_time()
    return SystemSnapshot(
        hostname=platform.node(),
        platform=platform.platform(),
        boot_time=boot,
        uptime_seconds=max(0.0, time.time() - boot),
        cpu=cpu_stats(per_core=per_core),
        memory=memory_stats(),
        swap=swap_stats(),
    )
