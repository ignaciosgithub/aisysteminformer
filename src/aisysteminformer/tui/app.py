"""Textual application: an interactive, tabbed system monitor.

The app keeps long-lived monitor objects (for accurate CPU% and throughput
deltas) and refreshes the visible tab on a timer. All data collection is
delegated to :mod:`aisysteminformer.core`; this module only handles rendering.
"""

from __future__ import annotations

from collections import deque

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.coordinate import Coordinate
from textual.widgets import (
    DataTable,
    Footer,
    Header,
    Label,
    Sparkline,
    Static,
    TabbedContent,
    TabPane,
)

from aisysteminformer.core import disk, formatting, network, processes, services, system

_HISTORY = 60  # Number of samples retained for the CPU sparkline.


class PerformancePane(Vertical):
    """CPU history sparkline plus memory / swap / load summaries."""

    def __init__(self) -> None:
        super().__init__()
        self._cpu_history: deque[float] = deque([0.0] * _HISTORY, maxlen=_HISTORY)

    def compose(self) -> ComposeResult:
        yield Label("CPU utilisation", id="cpu-label")
        yield Sparkline(list(self._cpu_history), id="cpu-spark")
        yield Static(id="mem-summary")

    def refresh_data(self) -> None:
        snap = system.snapshot()
        self._cpu_history.append(snap.cpu.percent_overall)
        spark = self.query_one("#cpu-spark", Sparkline)
        spark.data = list(self._cpu_history)

        load = snap.cpu.load_average
        load_text = (
            f"Load avg: {load[0]:.2f} {load[1]:.2f} {load[2]:.2f}\n" if load is not None else ""
        )
        self.query_one("#cpu-label", Label).update(
            f"CPU: {formatting.human_percent(snap.cpu.percent_overall)} "
            f"of {snap.cpu.logical_cores} logical cores "
            f"({snap.cpu.physical_cores} physical)"
        )
        self.query_one("#mem-summary", Static).update(
            f"Host: {snap.hostname}\n"
            f"Uptime: {formatting.human_duration(snap.uptime_seconds)}\n"
            f"{load_text}"
            f"Memory: {formatting.human_bytes(snap.memory.used)} / "
            f"{formatting.human_bytes(snap.memory.total)} "
            f"({formatting.human_percent(snap.memory.percent)})\n"
            f"Swap:   {formatting.human_bytes(snap.swap.used)} / "
            f"{formatting.human_bytes(snap.swap.total)} "
            f"({formatting.human_percent(snap.swap.percent)})"
        )


class ProcessPane(Vertical):
    """A sortable table of processes with a terminate action."""

    def __init__(self) -> None:
        super().__init__()
        self._monitor = processes.ProcessMonitor()

    def compose(self) -> ComposeResult:
        yield Label("Processes - press 'k' to terminate the selected row", id="proc-label")
        table: DataTable[str] = DataTable(id="proc-table")
        table.cursor_type = "row"
        table.add_columns("PID", "Name", "User", "CPU%", "Memory", "Mem%", "Thr", "Status")
        yield table

    def refresh_data(self) -> None:
        table = self.query_one("#proc-table", DataTable)
        previous = table.cursor_row
        table.clear()
        for proc in self._monitor.poll(limit=200):
            table.add_row(
                str(proc.pid),
                formatting.truncate(proc.name, 28),
                formatting.truncate(proc.username, 16),
                formatting.human_percent(proc.cpu_percent),
                formatting.human_bytes(proc.memory_rss),
                formatting.human_percent(proc.memory_percent),
                str(proc.num_threads),
                proc.status,
                key=str(proc.pid),
            )
        if previous is not None and 0 <= previous < table.row_count:
            table.move_cursor(row=previous)

    def selected_pid(self) -> int | None:
        table = self.query_one("#proc-table", DataTable)
        if table.row_count == 0:
            return None
        try:
            row_key = table.coordinate_to_cell_key(Coordinate(table.cursor_row, 0)).row_key
        except Exception:
            return None
        return int(row_key.value) if row_key.value is not None else None


class ConnectionsPane(Vertical):
    """A table of active network connections."""

    def compose(self) -> ComposeResult:
        yield Label("Network connections", id="net-label")
        table: DataTable[str] = DataTable(id="net-table")
        table.cursor_type = "row"
        table.add_columns("Proto", "Local", "Remote", "Status", "PID", "Process")
        yield table

    def refresh_data(self) -> None:
        table = self.query_one("#net-table", DataTable)
        table.clear()
        conns = network.list_connections()
        for conn in conns:
            table.add_row(
                conn.proto,
                conn.local_address,
                conn.remote_address or "-",
                conn.status or "-",
                str(conn.pid) if conn.pid is not None else "-",
                formatting.truncate(conn.process_name, 24) or "-",
            )
        suffix = "" if conns else " (none visible - may need elevated privileges)"
        self.query_one("#net-label", Label).update(f"Network connections: {len(conns)}{suffix}")


class DiskPane(Vertical):
    """Disk partition usage and live read/write rates."""

    def __init__(self) -> None:
        super().__init__()
        self._monitor = disk.DiskRateMonitor()

    def compose(self) -> ComposeResult:
        yield Label("Disk partitions", id="disk-label")
        parts: DataTable[str] = DataTable(id="disk-parts")
        parts.add_columns("Device", "Mount", "FS", "Used", "Total", "Use%")
        yield parts
        yield Label("Disk I/O", id="diskio-label")
        io: DataTable[str] = DataTable(id="disk-io")
        io.add_columns("Disk", "Read/s", "Write/s")
        yield io

    def refresh_data(self) -> None:
        parts = self.query_one("#disk-parts", DataTable)
        parts.clear()
        for part in disk.list_partitions():
            parts.add_row(
                part.device,
                part.mountpoint,
                part.fstype,
                formatting.human_bytes(part.used),
                formatting.human_bytes(part.total),
                formatting.human_percent(part.percent),
            )
        io = self.query_one("#disk-io", DataTable)
        io.clear()
        for rate in self._monitor.poll():
            io.add_row(
                rate.name,
                formatting.human_rate(rate.read_bytes_per_sec),
                formatting.human_rate(rate.write_bytes_per_sec),
            )


class ServicesPane(Vertical):
    """A table of system services (refreshed less frequently)."""

    def compose(self) -> ComposeResult:
        yield Label("Services", id="svc-label")
        table: DataTable[str] = DataTable(id="svc-table")
        table.cursor_type = "row"
        table.add_columns("Name", "Status", "Start/Load", "Description")
        yield table

    def refresh_data(self) -> None:
        table = self.query_one("#svc-table", DataTable)
        if not services.services_supported():
            self.query_one("#svc-label", Label).update("Services: unsupported on this platform")
            return
        rows = services.list_services()
        table.clear()
        for svc in rows:
            table.add_row(
                formatting.truncate(svc.name, 40),
                svc.status,
                svc.start_type,
                formatting.truncate(svc.description, 50),
            )
        self.query_one("#svc-label", Label).update(f"Services: {len(rows)}")


class SystemInformerApp(App[None]):
    """The top-level Textual application."""

    TITLE = "aisysteminformer"
    CSS = """
    Sparkline { height: 3; margin: 1 0; }
    DataTable { height: 1fr; }
    Label { padding: 1 0 0 0; text-style: bold; }
    #mem-summary { padding: 1 0; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "refresh_now", "Refresh"),
        ("k", "kill_selected", "Kill process"),
    ]

    def __init__(self, *, refresh_interval: float = 2.0) -> None:
        super().__init__()
        self._refresh_interval = refresh_interval
        self._services_counter = 0

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with TabbedContent(initial="tab-performance"):
            with TabPane("Performance", id="tab-performance"):
                yield PerformancePane()
            with TabPane("Processes", id="tab-processes"):
                yield ProcessPane()
            with TabPane("Network", id="tab-network"):
                yield ConnectionsPane()
            with TabPane("Disk", id="tab-disk"):
                yield DiskPane()
            with TabPane("Services", id="tab-services"):
                yield ServicesPane()
        yield Footer()

    def on_mount(self) -> None:
        self.action_refresh_now()
        self.set_interval(self._refresh_interval, self._tick)

    def _tick(self) -> None:
        self.query_one(PerformancePane).refresh_data()
        self.query_one(ProcessPane).refresh_data()
        self.query_one(ConnectionsPane).refresh_data()
        self.query_one(DiskPane).refresh_data()
        # Services change rarely and listing is comparatively expensive.
        self._services_counter += 1
        if self._services_counter % 5 == 0:
            self.query_one(ServicesPane).refresh_data()

    def action_refresh_now(self) -> None:
        self.query_one(PerformancePane).refresh_data()
        self.query_one(ProcessPane).refresh_data()
        self.query_one(ConnectionsPane).refresh_data()
        self.query_one(DiskPane).refresh_data()
        self.query_one(ServicesPane).refresh_data()

    def action_kill_selected(self) -> None:
        pane = self.query_one(ProcessPane)
        pid = pane.selected_pid()
        if pid is None:
            self.notify("No process selected", severity="warning")
            return
        result = processes.terminate_process(pid)
        self.notify(result.message, severity="information" if result.success else "error")
        pane.refresh_data()


def run() -> None:
    """Launch the interactive application."""

    SystemInformerApp().run()


if __name__ == "__main__":  # pragma: no cover
    run()
