"""Network connection enumeration and per-NIC throughput."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass

import psutil

_SOCKET_TYPE_NAMES = {
    socket.SOCK_STREAM: "TCP",
    socket.SOCK_DGRAM: "UDP",
}

#: Connection kinds accepted by :func:`psutil.net_connections`.
VALID_KINDS = (
    "inet",
    "inet4",
    "inet6",
    "tcp",
    "tcp4",
    "tcp6",
    "udp",
    "udp4",
    "udp6",
    "unix",
    "all",
)


@dataclass(frozen=True)
class Connection:
    """A single network connection (socket) and its owning process."""

    family: str
    proto: str
    status: str
    local_address: str
    remote_address: str
    pid: int | None
    process_name: str


@dataclass(frozen=True)
class InterfaceRate:
    """Bytes/sec sent and received on a network interface since the last sample."""

    name: str
    bytes_sent_per_sec: float
    bytes_recv_per_sec: float
    bytes_sent_total: int
    bytes_recv_total: int


def _format_addr(addr: object) -> str:
    """Render a psutil ``addr`` namedtuple as ``host:port`` (or ``""``)."""

    if not addr:
        return ""
    ip = getattr(addr, "ip", "") or ""
    port = getattr(addr, "port", None)
    if ":" in ip and port is not None:  # IPv6: bracket the address.
        return f"[{ip}]:{port}"
    if port is not None:
        return f"{ip}:{port}"
    return ip


def list_connections(*, kind: str = "inet") -> list[Connection]:
    """Return active network connections.

    ``kind`` is passed through to :func:`psutil.net_connections` (e.g. ``inet``,
    ``tcp``, ``udp``). Resolving connections for processes owned by other users
    typically requires elevated privileges; inaccessible entries are skipped.
    """

    try:
        raw = psutil.net_connections(kind=kind)
    except psutil.AccessDenied:
        return []

    name_cache: dict[int, str] = {}
    connections: list[Connection] = []
    for conn in raw:
        pid = conn.pid
        proc_name = ""
        if pid is not None:
            if pid in name_cache:
                proc_name = name_cache[pid]
            else:
                try:
                    proc_name = psutil.Process(pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    proc_name = ""
                name_cache[pid] = proc_name
        connections.append(
            Connection(
                family=conn.family.name if hasattr(conn.family, "name") else str(conn.family),
                proto=_SOCKET_TYPE_NAMES.get(conn.type, str(conn.type)),
                status=conn.status or "",
                local_address=_format_addr(conn.laddr),
                remote_address=_format_addr(conn.raddr),
                pid=pid,
                process_name=proc_name,
            )
        )
    return connections


class NetworkRateMonitor:
    """Compute per-interface throughput between successive :meth:`poll` calls."""

    def __init__(self) -> None:
        self._last_counters: dict[str, psutil._ntuples.snetio] = {}
        self._last_time: float | None = None

    def poll(self) -> list[InterfaceRate]:
        """Return throughput for each interface since the previous poll."""

        now = time.monotonic()
        counters = psutil.net_io_counters(pernic=True)
        elapsed = (now - self._last_time) if self._last_time is not None else 0.0
        rates: list[InterfaceRate] = []
        for name, current in counters.items():
            previous = self._last_counters.get(name)
            if previous is not None and elapsed > 0:
                sent_rate = max(0.0, (current.bytes_sent - previous.bytes_sent) / elapsed)
                recv_rate = max(0.0, (current.bytes_recv - previous.bytes_recv) / elapsed)
            else:
                sent_rate = recv_rate = 0.0
            rates.append(
                InterfaceRate(
                    name=name,
                    bytes_sent_per_sec=sent_rate,
                    bytes_recv_per_sec=recv_rate,
                    bytes_sent_total=current.bytes_sent,
                    bytes_recv_total=current.bytes_recv,
                )
            )
        self._last_counters = counters
        self._last_time = now
        rates.sort(key=lambda r: r.name)
        return rates
