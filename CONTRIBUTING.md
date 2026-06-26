# Contributing

Thanks for your interest in improving `aisysteminformer`. This document covers
the development workflow and the quality bar enforced by CI.

## Development setup

Requires Python 3.10 or newer.

```bash
git clone https://github.com/ignaciosgithub/aisysteminformer.git
cd aisysteminformer
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install                 # run lint/type/security checks on commit
```

## Quality checks

All of these run in CI on Python 3.10, 3.11 and 3.12; run them locally before
pushing:

```bash
ruff check src/ tests/             # lint (also: ruff format for formatting)
mypy src/                          # static type checking
pytest                             # tests + coverage gate (>= 85%)
bandit -r src/ -c pyproject.toml   # static security analysis
pip-audit                          # dependency vulnerability audit
```

`pre-commit` wires the first four into a git hook so they run automatically on
changed files; the full matrix and the security/audit jobs run in CI.

## Coding guidelines

- **Keep collection in `core/`.** UI modules (`cli.py`, `tui/`) should call
  `core` functions and render the result — they must not call `psutil`
  directly. This keeps the data layer testable and the UIs thin.
- **Return immutable dataclasses** from `core` functions, never raw `psutil`
  objects. Add new fields as typed dataclass attributes.
- **Type everything.** `mypy` runs with `disallow_untyped_defs`; all public
  functions need full annotations.
- **Write a docstring** for every public function/class describing what it
  returns and any platform-specific behavior.
- **No `shell=True`.** Any new subprocess call must use a fixed argument list
  and validate untrusted input against an allow-list.
- **Handle missing privileges** by catching `psutil.AccessDenied` /
  `NoSuchProcess` at the boundary and degrading gracefully.

## Tests

- Add or update tests under `tests/` for any behavior change. Coverage must stay
  at or above 85% (the interactive Textual UI is excluded from the gate, since
  it is exercised manually).
- Prefer mocking `psutil` / `subprocess` so tests are deterministic and do not
  depend on the host's live process table.

## Commits and pull requests

- Keep changes focused; one logical change per pull request where practical.
- Ensure the full check suite above passes locally before opening a PR.
- CI must be green on all three Python versions before merge.
