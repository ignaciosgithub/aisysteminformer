from __future__ import annotations

from aisysteminformer.core import system


def test_snapshot_basic_invariants() -> None:
    snap = system.snapshot()
    assert snap.hostname != ""
    assert snap.platform != ""
    assert snap.boot_time > 0
    assert snap.uptime_seconds >= 0

    assert 0.0 <= snap.cpu.percent_overall <= 100.0 * max(1, snap.cpu.logical_cores)
    assert snap.cpu.logical_cores >= 1

    assert snap.memory.total > 0
    assert 0 <= snap.memory.used <= snap.memory.total
    assert 0.0 <= snap.memory.percent <= 100.0

    assert snap.swap.total >= 0
    assert 0.0 <= snap.swap.percent <= 100.0


def test_cpu_stats_per_core_lengths() -> None:
    stats = system.cpu_stats(per_core=True)
    if stats.percent_per_core:
        assert len(stats.percent_per_core) >= 1
        assert all(0.0 <= v <= 100.0 for v in stats.percent_per_core)

    no_core = system.cpu_stats(per_core=False)
    assert no_core.percent_per_core == []


def test_memory_and_swap_consistency() -> None:
    mem = system.memory_stats()
    assert mem.available <= mem.total
    swap = system.swap_stats()
    assert swap.used <= swap.total or swap.total == 0
