# Security Policy

## Supported versions

`aisysteminformer` is pre-1.0; security fixes are applied to the `main` branch
and released in the next tagged version.

## Reporting a vulnerability

Please report suspected vulnerabilities privately via GitHub Security Advisories
("Report a vulnerability" on the repository's **Security** tab) rather than
opening a public issue. We aim to acknowledge reports within a few days.

## Security design

The tool is designed so that the only operations with security impact are
explicit and auditable.

### No shell execution

There is exactly one place that spawns external processes — `core/services.py`,
which calls `systemctl` (Linux) or `sc` (Windows). Every invocation:

- passes a **fixed argument list** to `subprocess.run`; `shell=True` is never
  used, so there is no shell-injection surface;
- only ever runs a hard-coded executable name with allow-listed sub-commands;
- validates the requested action against `VALID_ACTIONS`
  (`start`/`stop`/`restart`) before doing anything — any other value is rejected
  and logged;
- runs with `timeout=15` and `check=False` so a hung or failing helper cannot
  block or crash the tool.

The `bandit` configuration skips `B404`/`B603` for this module specifically
because the generic "subprocess" warnings do not apply to fixed, validated
argument lists; all other `bandit` checks remain active and run in CI.

### Least privilege and graceful degradation

- The tool requests no elevation. Data that requires privileges you do not have
  (e.g. connections or process details owned by other users) is simply omitted
  rather than causing a crash — `psutil.AccessDenied` / `NoSuchProcess` are
  caught at every boundary.
- Mutating operations (process termination, service control) are never implicit.
  They happen only when the user explicitly invokes `kill` / a service action,
  and each one is written to the audit log (see below).

### No network, no telemetry, no credentials

The application makes no outbound network connections of its own, collects no
telemetry, and never reads or stores credentials.

### Input validation

- Service actions are checked against an allow-list before dispatch.
- CLI arguments are parsed and constrained by `argparse` (choices, integer
  types). Sort keys for the process list are validated against the known set.

### Auditability

Mutating operations emit structured log records via the standard `logging`
module (configured in `logconfig.py`). Logs are written to **stderr** so they
never corrupt machine-readable `--json` output on stdout. Increase verbosity
with `-v` (info) or `-vv` (debug).

## Supply chain

- Runtime dependencies are constrained to audited major ranges
  (`psutil`, `textual`) in `pyproject.toml`.
- CI runs `pip-audit` to flag known-vulnerable dependencies and `bandit` for
  static security analysis on every push and pull request.
