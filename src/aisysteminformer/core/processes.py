"""Process enumeration, inspection and (guarded) control."""

from __future__ import annotations

from dataclasses import dataclass

import psutil

# Fields requested from psutil in a single ``oneshot()`` for efficiency.
_PROC_ATTRS = (
    "pid",
    "ppid",
    "name",
    "username",
    "status",
    "cpu_percent",
    "memory_info",
    "memory_percent",
    "num_threads",
    "create_time",
)


@dataclass(frozen=True)
class ProcessInfo:
    """A snapshot of a single process."""

    pid: int
    ppid: int
    name: str
    username: str
    status: str
    cpu_percent: float
    memory_rss: int
    memory_percent: float
    num_threads: int
    create_time: float


@dataclass(frozen=True)
class TerminationResult:
    """Outcome of an attempt to stop a process."""

    pid: int
    success: bool
    message: str


def _to_info(proc: psutil.Process) -> ProcessInfo | None:
    """Convert a live ``psutil.Process`` into an immutable :class:`ProcessInfo`.

    Returns ``None`` if the process vanished or is inaccessible while reading.
    """

    try:
        with proc.oneshot():
            info = proc.as_dict(attrs=_PROC_ATTRS)
            mem = info.get("memory_info")
            return ProcessInfo(
                pid=info["pid"],
                ppid=info.get("ppid") or 0,
                name=info.get("name") or "",
                username=info.get("username") or "",
                status=info.get("status") or "",
                cpu_percent=float(info.get("cpu_percent") or 0.0),
                memory_rss=int(getattr(mem, "rss", 0) or 0),
                memory_percent=float(info.get("memory_percent") or 0.0),
                num_threads=int(info.get("num_threads") or 0),
                create_time=float(info.get("create_time") or 0.0),
            )
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def list_processes(
    *,
    sort_by: str = "cpu_percent",
    descending: bool = True,
    limit: int | None = None,
    name_filter: str | None = None,
) -> list[ProcessInfo]:
    """Return a snapshot list of running processes.

    ``sort_by`` is any :class:`ProcessInfo` field name. ``name_filter`` performs
    a case-insensitive substring match against the process name.
    """

    needle = name_filter.lower() if name_filter else None
    processes: list[ProcessInfo] = []
    for proc in psutil.process_iter():
        info = _to_info(proc)
        if info is None:
            continue
        if needle is not None and needle not in info.name.lower():
            continue
        processes.append(info)

    key = sort_by if sort_by in ProcessInfo.__annotations__ else "cpu_percent"
    processes.sort(key=lambda p: getattr(p, key), reverse=descending)
    if limit is not None and limit >= 0:
        processes = processes[:limit]
    return processes


def get_process(pid: int) -> ProcessInfo | None:
    """Return info for a single PID, or ``None`` if it is gone/inaccessible."""

    try:
        return _to_info(psutil.Process(pid))
    except (psutil.NoSuchProcess, psutil.AccessDenied, ValueError):
        return None


def terminate_process(pid: int, *, force: bool = False, timeout: float = 3.0) -> TerminationResult:
    """Politely terminate (SIGTERM) or, with ``force``, kill (SIGKILL) a process.

    The caller is responsible for confirming intent; this function performs no
    interactive prompting so it stays testable and side-effect-explicit.
    """

    try:
        proc = psutil.Process(pid)
    except (psutil.NoSuchProcess, ValueError):
        return TerminationResult(pid, False, "no such process")

    name = proc.name()
    try:
        if force:
            proc.kill()
        else:
            proc.terminate()
        proc.wait(timeout=timeout)
    except psutil.AccessDenied:
        return TerminationResult(pid, False, f"access denied stopping {name!r}")
    except psutil.TimeoutExpired:
        return TerminationResult(
            pid, False, f"{name!r} did not exit within {timeout:g}s (try --force)"
        )
    except psutil.NoSuchProcess:
        # It exited between the lookup and the signal: treat as success.
        pass
    verb = "killed" if force else "terminated"
    return TerminationResult(pid, True, f"{verb} {name!r} (pid {pid})")


class ProcessMonitor:
    """Stateful helper that yields per-process CPU% across repeated polls.

    ``psutil`` computes a process's CPU percentage relative to the previous call
    on the *same* :class:`~psutil.Process` object, so the TUI keeps one monitor
    instance alive and calls :meth:`poll` on a timer.
    """

    def __init__(self) -> None:
        self._cache: dict[int, psutil.Process] = {}

    def poll(
        self,
        *,
        sort_by: str = "cpu_percent",
        descending: bool = True,
        limit: int | None = None,
    ) -> list[ProcessInfo]:
        """Return a fresh snapshot, reusing cached handles for accurate CPU%."""

        seen: set[int] = set()
        results: list[ProcessInfo] = []
        for proc in psutil.process_iter(["pid"]):
            pid = proc.info["pid"]
            seen.add(pid)
            cached = self._cache.get(pid)
            if cached is None:
                cached = proc
                self._cache[pid] = cached
            info = _to_info(cached)
            if info is not None:
                results.append(info)

        for dead_pid in [pid for pid in self._cache if pid not in seen]:
            self._cache.pop(dead_pid, None)

        key = sort_by if sort_by in ProcessInfo.__annotations__ else "cpu_percent"
        results.sort(key=lambda p: getattr(p, key), reverse=descending)
        if limit is not None and limit >= 0:
            results = results[:limit]
        return results
