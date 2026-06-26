# Architecture

`aisysteminformer` separates **data collection** from **presentation** so the
same logic backs both the scriptable CLI and the interactive TUI, and so the
collection layer is fully unit-testable without a terminal.

```
                 +-------------------+        +-------------------+
                 |   cli.py (Rich)   |        |  tui/app.py       |
                 |  one-shot output  |        |  (Textual panes)  |
                 +---------+---------+        +---------+---------+
                           |                            |
                           +-------------+--------------+
                                         |
                              +----------v-----------+
                              |        core/         |
                              |  UI-agnostic data    |
                              |  collection (psutil) |
                              +----------------------+
```

## Layers

### `core/` — data collection

Pure, UI-agnostic functions and small stateful monitors built on `psutil`.
Every public function returns **immutable, frozen dataclasses** (e.g.
`ProcessInfo`, `Connection`, `PartitionUsage`, `ServiceInfo`) or plain values —
never `psutil` objects — so callers cannot accidentally trigger lazy syscalls or
mutate shared state.

| Module          | Responsibility |
|-----------------|----------------|
| `system.py`     | CPU (overall/per-core), load average, memory and swap snapshot |
| `processes.py`  | Process listing, lookup, terminate; `ProcessMonitor` for CPU% deltas |
| `network.py`    | Connection listing; `NetworkRateMonitor` for throughput deltas |
| `disk.py`       | Partition usage; `DiskRateMonitor` for I/O throughput deltas |
| `files.py`      | Find processes referencing a given path (`whohas`) |
| `services.py`   | Cross-platform service enumeration / control |
| `formatting.py` | Human-readable bytes / rates / durations / percentages |
| `serialization.py` | Recursively convert dataclasses to JSON-safe primitives |

#### Stateful monitors

Rates and process CPU% are **deltas between two samples**, which requires state
between polls. That state is encapsulated in small monitor classes
(`ProcessMonitor`, `NetworkRateMonitor`, `DiskRateMonitor`) rather than scattered
through the UI, so:

- the first poll establishes a baseline and subsequent polls report real rates;
- `ProcessMonitor` caches `psutil.Process` objects keyed by PID, so per-process
  CPU% is accurate and a process that exits is pruned cleanly;
- both the CLI and the TUI reuse the identical computation.

### `cli.py` — scriptable command line

`argparse`-based. Each sub-command (`system`, `processes`, `network`, `disk`,
`services`, `whohas`, `kill`) maps to a small `_cmd_*` function. Two global flags
cut across all of them:

- `--json` emits machine-readable JSON (via `serialization.dumps`) on **stdout**;
- `-v` / `-vv` raise log verbosity (info / debug) on **stderr**.

Keeping logs on stderr guarantees `--json` output is never corrupted by
diagnostics and can be piped directly into `jq` or other tooling.

### `tui/app.py` — interactive dashboard

A Textual app with one tab per domain. The refresh tick only polls the
**currently visible** tab, so hidden panes never spend syscalls
(`process_iter`, `net_connections`, partition scans) collecting data the user
cannot see. The services tab — which shells out to `systemctl` — refreshes on a
slower cadence than the live performance/process views.

## Data flow (one CLI invocation)

```
argv -> argparse -> _cmd_<name>() -> core.<module>.<collector>()
     -> psutil syscalls (batched via oneshot()/process_iter attrs)
     -> frozen dataclass(es)
     -> Rich table  (default)   OR   serialization.dumps() -> JSON (--json)
```

## Design principles

- **One source of truth per datum** — collection lives only in `core/`.
- **Immutability** — frozen dataclasses prevent accidental mutation and make
  outputs trivially serializable and testable.
- **Batch syscalls** — `processes.py` uses a single `process_iter(attrs=...)`
  pass with `oneshot()` rather than N per-process queries; `network.py` caches
  PID→name lookups within a single listing.
- **Graceful degradation** — `AccessDenied` / `NoSuchProcess` are caught at the
  boundary; missing privileges drop rows instead of crashing.
- **Explicit side effects** — the only mutating operations (terminate, service
  control) are user-invoked and audit-logged.
