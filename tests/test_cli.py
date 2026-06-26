from __future__ import annotations

import pytest

from aisysteminformer import cli


@pytest.mark.parametrize(
    "argv",
    [
        ["system"],
        ["sys"],
        ["processes", "--limit", "3"],
        ["ps", "-n", "3", "-s", "memory_rss"],
        ["network"],
        ["net", "--kind", "tcp"],
        ["disk"],
        ["services"],
        ["whohas", "/nonexistent/path/xyz"],
    ],
)
def test_cli_oneshot_commands_exit_zero(argv: list[str]) -> None:
    assert cli.main(argv) == 0


def test_cli_kill_missing_pid_exits_one() -> None:
    assert cli.main(["kill", "-12345"]) == 1


def test_cli_version_exits_zero() -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["--version"])
    assert exc.value.code == 0
