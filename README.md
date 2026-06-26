# aisysteminformer

A free, cross-platform, terminal-based tool for monitoring system resources,
inspecting processes, network connections, disk activity and system services.

It offers two ways to look at the same data:

- an **interactive TUI** (a tabbed, auto-refreshing dashboard), and
- **scriptable one-shot CLI commands** for quick checks and automation.

All data collection lives in a small, UI-agnostic `core` layer built on
[`psutil`](https://github.com/giampaolo/psutil); the CLI and TUI are thin
presentation layers over it.

> This is an original implementation written from scratch. It takes functional
> inspiration from classic task-manager / system-monitor tools but contains no
> third-party application code.

## Features

- **Performance** – CPU utilisation (overall and per-core), a live CPU history
  sparkline, load averages, memory and swap usage.
- **Processes** – sortable, filterable process list (PID, name, user, CPU%,
  memory, threads, status) with a guarded terminate/kill action.
- **Network** – active TCP/UDP connections with local/remote addresses, state
  and owning process.
- **Disk** – partition usage plus per-disk read/write throughput.
- **Services** – system services (Windows service manager via `psutil`; Linux
  via `systemctl` when available).
- **whohas** – find which processes currently reference a given file or path.

## Installation

Requires Python 3.10 or newer.

```bash
git clone https://github.com/ignaciosgithub/aisysteminformer.git
cd aisysteminformer
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

For development (tests, linting, type checking):

```bash
pip install -e ".[dev]"
```

## Usage

Launch the interactive TUI (the default when run with no arguments):

```bash
aisysteminformer
# or explicitly
aisysteminformer tui
```

TUI key bindings:

| Key | Action                         |
|-----|--------------------------------|
| `q` | Quit                           |
| `r` | Refresh now                    |
| `k` | Terminate the selected process |

### One-shot CLI commands

```bash
aisysteminformer system                 # CPU / memory / swap overview (alias: sys)
aisysteminformer processes -n 15 -s memory_rss   # top processes (alias: ps)
aisysteminformer processes -f python    # filter by name substring
aisysteminformer network                # active connections (alias: net)
aisysteminformer disk                   # partitions and I/O totals
aisysteminformer services               # system services (alias: svc)
aisysteminformer whohas /path/to/file   # processes referencing a path
aisysteminformer kill <pid>             # SIGTERM a process
aisysteminformer kill <pid> --force     # SIGKILL a process
```

You can also run the package directly without installing the console script:

```bash
python -m aisysteminformer system
```

## Architecture

```
src/aisysteminformer/
  core/            UI-agnostic data collection (no rendering, fully testable)
    system.py        CPU / memory / swap / uptime snapshot
    processes.py     process listing, lookup, terminate; ProcessMonitor (CPU% deltas)
    network.py       connection listing; NetworkRateMonitor (throughput deltas)
    disk.py          partition usage; DiskRateMonitor (I/O throughput deltas)
    files.py         find processes referencing a path
    services.py      cross-platform service enumeration / control
    formatting.py    human-readable bytes / rates / durations / percentages
  cli.py           argparse-based command line (Rich tables)
  tui/app.py       Textual tabbed dashboard
```

The `core` modules return immutable dataclasses (`ProcessInfo`, `Connection`,
`PartitionUsage`, …). Rate/CPU% calculations that depend on deltas between
samples are encapsulated in small stateful monitor classes so the same logic is
reused by both the CLI and the TUI.

## Security & design notes

- No `shell=True`; the only subprocess calls (Linux `systemctl`) use fixed
  argument lists, so there is no shell-injection surface.
- Process termination is explicit and never prompts implicitly, keeping it
  testable and side-effect-explicit. Operations that require elevated
  privileges degrade gracefully (e.g. connections you cannot see are simply
  omitted) rather than crashing.
- No telemetry, no network calls of its own, no credential handling.

## Development

```bash
ruff check src/ tests/     # lint
mypy src/                  # type check
pytest                     # tests
```

Continuous integration runs all three on every push and pull request.

## License

[MIT](LICENSE)
