from __future__ import annotations

import os
import subprocess
import sys
import time

import psutil
import pytest

from aisysteminformer.core import processes


def test_list_processes_includes_self() -> None:
    pids = {p.pid for p in processes.list_processes(limit=None)}
    assert os.getpid() in pids


def test_list_processes_limit_and_sort() -> None:
    rows = processes.list_processes(sort_by="memory_rss", limit=5)
    assert len(rows) <= 5
    memories = [r.memory_rss for r in rows]
    assert memories == sorted(memories, reverse=True)


def test_list_processes_invalid_sort_falls_back() -> None:
    rows = processes.list_processes(sort_by="does_not_exist", limit=3)
    assert isinstance(rows, list)


def test_get_process_self() -> None:
    info = processes.get_process(os.getpid())
    assert info is not None
    assert info.pid == os.getpid()


def test_get_process_missing() -> None:
    assert processes.get_process(-1) is None


def test_process_monitor_poll_twice() -> None:
    monitor = processes.ProcessMonitor()
    first = monitor.poll(limit=10)
    time.sleep(0.05)
    second = monitor.poll(limit=10)
    assert isinstance(first, list)
    assert isinstance(second, list)


def _spawn_sleeper() -> subprocess.Popen[bytes]:
    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])


def test_terminate_process_real_child() -> None:
    child = _spawn_sleeper()
    try:
        result = processes.terminate_process(child.pid, timeout=5.0)
        assert result.success, result.message
        assert not psutil.pid_exists(child.pid) or psutil.Process(child.pid).status() in {
            psutil.STATUS_ZOMBIE,
            psutil.STATUS_DEAD,
        }
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_terminate_process_force_real_child() -> None:
    child = _spawn_sleeper()
    try:
        result = processes.terminate_process(child.pid, force=True, timeout=5.0)
        assert result.success, result.message
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_terminate_missing_process() -> None:
    result = processes.terminate_process(-12345)
    assert result.success is False
    assert "no such process" in result.message


@pytest.mark.skipif(os.name != "posix", reason="zombie reaping is POSIX-specific")
def test_terminate_reaps_child_status() -> None:
    child = _spawn_sleeper()
    processes.terminate_process(child.pid, timeout=5.0)
    child.wait(timeout=5)
