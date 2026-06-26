"""Command-line interface for aisysteminformer.

Running ``aisysteminformer`` with no sub-command launches the interactive TUI.
The sub-commands provide scriptable, one-shot access to the same data.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from rich.console import Console
from rich.table import Table

from aisysteminformer import __version__
from aisysteminformer.core import (
    disk,
    files,
    formatting,
    network,
    processes,
    serialization,
    services,
    system,
)
from aisysteminformer.logconfig import configure_logging

_console = Console()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aisysteminformer",
        description="Monitor system resources, processes, network, disk and services.",
    )
    parser.add_argument("--version", action="version", version=f"aisysteminformer {__version__}")
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit machine-readable JSON instead of formatted tables",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase log verbosity (-v for info, -vv for debug); logs go to stderr",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tui", help="launch the interactive terminal UI (default)")
    sub.add_parser("system", aliases=["sys"], help="show a system resource overview")

    ps = sub.add_parser("processes", aliases=["ps"], help="list running processes")
    ps.add_argument("-n", "--limit", type=int, default=20, help="max rows to show (default 20)")
    ps.add_argument(
        "-s",
        "--sort",
        default="cpu_percent",
        choices=sorted(processes.ProcessInfo.__annotations__),
        help="field to sort by (default cpu_percent)",
    )
    ps.add_argument("-f", "--filter", default=None, help="case-insensitive name substring filter")

    net = sub.add_parser("network", aliases=["net"], help="list active network connections")
    net.add_argument(
        "-k",
        "--kind",
        default="inet",
        choices=network.VALID_KINDS,
        metavar="KIND",
        help="connection kind: inet, tcp, udp, unix, all (default inet)",
    )

    sub.add_parser("disk", help="show disk partitions and I/O totals")
    sub.add_parser("services", aliases=["svc"], help="list system services")

    who = sub.add_parser("whohas", help="find processes that have a file/path open")
    who.add_argument("path", help="file or directory path to look up")

    kill = sub.add_parser("kill", help="terminate a process by PID")
    kill.add_argument("pid", type=int, help="process id to stop")
    kill.add_argument(
        "--force", action="store_true", help="forcefully kill (SIGKILL) instead of SIGTERM"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point. Returns a process exit code."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)
    command = args.command or "tui"
    as_json: bool = args.json

    if command == "tui":
        return _run_tui()
    if command in ("system", "sys"):
        return _cmd_system(as_json)
    if command in ("processes", "ps"):
        return _cmd_processes(args.limit, args.sort, args.filter, as_json)
    if command in ("network", "net"):
        return _cmd_network(args.kind, as_json)
    if command == "disk":
        return _cmd_disk(as_json)
    if command in ("services", "svc"):
        return _cmd_services(as_json)
    if command == "whohas":
        return _cmd_whohas(args.path, as_json)
    if command == "kill":
        return _cmd_kill(args.pid, args.force, as_json)
    parser.print_help()
    return 2


def _emit_json(payload: object) -> int:
    """Print ``payload`` as JSON on stdout and return a success exit code."""

    print(serialization.dumps(payload))
    return 0


def _run_tui() -> int:
    try:
        from aisysteminformer.tui.app import run as run_tui
    except ImportError as exc:  # pragma: no cover - only without the textual extra.
        _console.print(f"[red]TUI unavailable:[/] {exc}")
        _console.print("Install the UI dependency with: [bold]pip install textual[/]")
        return 1
    run_tui()
    return 0


def _cmd_system(as_json: bool = False) -> int:
    snap = system.snapshot()
    if as_json:
        return _emit_json(snap)
    _console.print(f"[bold]{snap.hostname}[/]  {snap.platform}")
    _console.print(f"Uptime: {formatting.human_duration(snap.uptime_seconds)}")
    load = snap.cpu.load_average
    load_text = (
        f"  load avg: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}" if load is not None else ""
    )
    _console.print(
        f"CPU: {formatting.human_percent(snap.cpu.percent_overall)} of "
        f"{snap.cpu.logical_cores} logical cores{load_text}"
    )
    _console.print(
        f"Memory: {formatting.human_bytes(snap.memory.used)} / "
        f"{formatting.human_bytes(snap.memory.total)} "
        f"({formatting.human_percent(snap.memory.percent)})"
    )
    _console.print(
        f"Swap: {formatting.human_bytes(snap.swap.used)} / "
        f"{formatting.human_bytes(snap.swap.total)} "
        f"({formatting.human_percent(snap.swap.percent)})"
    )
    return 0


def _cmd_processes(
    limit: int, sort_by: str, name_filter: str | None, as_json: bool = False
) -> int:
    rows = processes.list_processes(sort_by=sort_by, limit=limit, name_filter=name_filter)
    if as_json:
        return _emit_json(rows)
    table = Table(title=f"Top {len(rows)} processes (by {sort_by})")
    table.add_column("PID", justify="right")
    table.add_column("Name")
    table.add_column("User")
    table.add_column("CPU%", justify="right")
    table.add_column("Memory", justify="right")
    table.add_column("Mem%", justify="right")
    table.add_column("Threads", justify="right")
    table.add_column("Status")
    for proc in rows:
        table.add_row(
            str(proc.pid),
            formatting.truncate(proc.name, 28),
            formatting.truncate(proc.username, 16),
            formatting.human_percent(proc.cpu_percent),
            formatting.human_bytes(proc.memory_rss),
            formatting.human_percent(proc.memory_percent),
            str(proc.num_threads),
            proc.status,
        )
    _console.print(table)
    return 0


def _cmd_network(kind: str, as_json: bool = False) -> int:
    conns = network.list_connections(kind=kind)
    if as_json:
        return _emit_json(conns)
    table = Table(title=f"Network connections ({kind})")
    table.add_column("Proto")
    table.add_column("Local address")
    table.add_column("Remote address")
    table.add_column("Status")
    table.add_column("PID", justify="right")
    table.add_column("Process")
    for conn in conns:
        table.add_row(
            conn.proto,
            conn.local_address,
            conn.remote_address or "-",
            conn.status or "-",
            str(conn.pid) if conn.pid is not None else "-",
            formatting.truncate(conn.process_name, 24) or "-",
        )
    _console.print(table)
    if not conns:
        _console.print("[yellow]No connections listed (try running with elevated privileges).[/]")
    return 0


def _cmd_disk(as_json: bool = False) -> int:
    partitions = disk.list_partitions()
    io = disk.DiskRateMonitor().poll()
    if as_json:
        return _emit_json({"partitions": partitions, "io": io})
    table = Table(title="Disk partitions")
    table.add_column("Device")
    table.add_column("Mount")
    table.add_column("FS")
    table.add_column("Used", justify="right")
    table.add_column("Total", justify="right")
    table.add_column("Use%", justify="right")
    for part in partitions:
        table.add_row(
            part.device,
            part.mountpoint,
            part.fstype,
            formatting.human_bytes(part.used),
            formatting.human_bytes(part.total),
            formatting.human_percent(part.percent),
        )
    _console.print(table)

    if io:
        io_table = Table(title="Disk I/O totals")
        io_table.add_column("Disk")
        io_table.add_column("Read", justify="right")
        io_table.add_column("Written", justify="right")
        for rate in io:
            io_table.add_row(
                rate.name,
                formatting.human_bytes(rate.read_bytes_total),
                formatting.human_bytes(rate.write_bytes_total),
            )
        _console.print(io_table)
    return 0


def _cmd_services(as_json: bool = False) -> int:
    if not services.services_supported():
        if as_json:
            return _emit_json([])
        _console.print("[yellow]Service inspection is not available on this platform.[/]")
        return 0
    rows = services.list_services()
    if as_json:
        return _emit_json(rows)
    table = Table(title=f"Services ({len(rows)})")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Start/Load")
    table.add_column("Description")
    for svc in rows:
        table.add_row(
            formatting.truncate(svc.name, 36),
            svc.status,
            svc.start_type,
            formatting.truncate(svc.description, 48),
        )
    _console.print(table)
    return 0


def _cmd_whohas(path: str, as_json: bool = False) -> int:
    holders = files.find_processes_using_path(path)
    if as_json:
        return _emit_json(holders)
    if not holders:
        _console.print(
            f"No accessible process references [bold]{path}[/] "
            "(it may be free, or require elevated privileges to see)."
        )
        return 0
    table = Table(title=f"Processes referencing {path}")
    table.add_column("PID", justify="right")
    table.add_column("Process")
    table.add_column("Reference")
    table.add_column("Path")
    for holder in holders:
        table.add_row(str(holder.pid), holder.process_name, holder.reference, holder.path)
    _console.print(table)
    return 0


def _cmd_kill(pid: int, force: bool, as_json: bool = False) -> int:
    result = processes.terminate_process(pid, force=force)
    if as_json:
        print(serialization.dumps(result))
        return 0 if result.success else 1
    if result.success:
        _console.print(f"[green]{result.message}[/]")
        return 0
    _console.print(f"[red]Failed:[/] {result.message}")
    return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
