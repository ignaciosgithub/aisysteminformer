from __future__ import annotations

import time

from aisysteminformer.core import disk, network, services


def test_list_connections_returns_list() -> None:
    conns = network.list_connections()
    assert isinstance(conns, list)
    for conn in conns:
        assert conn.proto in {"TCP", "UDP"} or conn.proto
        assert isinstance(conn.local_address, str)
        assert conn.pid is None or isinstance(conn.pid, int)


def test_network_rate_monitor_poll() -> None:
    monitor = network.NetworkRateMonitor()
    first = monitor.poll()
    assert all(r.bytes_sent_per_sec == 0.0 for r in first)  # first poll has no delta
    time.sleep(0.05)
    second = monitor.poll()
    assert isinstance(second, list)
    for rate in second:
        assert rate.bytes_sent_per_sec >= 0.0
        assert rate.bytes_recv_per_sec >= 0.0


def test_list_partitions() -> None:
    parts = disk.list_partitions()
    assert isinstance(parts, list)
    for part in parts:
        assert part.total >= 0
        assert 0.0 <= part.percent <= 100.0
        assert part.used <= part.total


def test_disk_rate_monitor_poll() -> None:
    monitor = disk.DiskRateMonitor()
    first = monitor.poll()
    assert isinstance(first, list)
    time.sleep(0.05)
    second = monitor.poll()
    for rate in second:
        assert rate.read_bytes_per_sec >= 0.0
        assert rate.write_bytes_per_sec >= 0.0


def test_services_supported_is_bool() -> None:
    assert isinstance(services.services_supported(), bool)


def test_list_services_returns_list() -> None:
    rows = services.list_services()
    assert isinstance(rows, list)
    if rows:
        assert all(s.name for s in rows)


def test_control_service_rejects_invalid_action() -> None:
    result = services.control_service("whatever", "frobnicate")
    assert result.success is False
    assert "invalid action" in result.message
