from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

import pytest

from aisysteminformer import cli
from aisysteminformer.core import serialization, services
from aisysteminformer.logconfig import LOGGER_NAME, configure_logging


@dataclass(frozen=True)
class _Nested:
    value: int


@dataclass(frozen=True)
class _Sample:
    name: str
    nested: _Nested
    items: tuple[int, ...]


def test_to_jsonable_converts_dataclass_tree() -> None:
    out = serialization.to_jsonable(_Sample("x", _Nested(3), (1, 2)))
    assert out == {"name": "x", "nested": {"value": 3}, "items": [1, 2]}


def test_to_jsonable_handles_mappings_and_sets() -> None:
    assert serialization.to_jsonable({1: "a"}) == {"1": "a"}
    assert sorted(serialization.to_jsonable({1, 2})) == [1, 2]


def test_to_jsonable_passes_primitives_through() -> None:
    assert serialization.to_jsonable(None) is None
    assert serialization.to_jsonable(4.5) == 4.5


def test_dumps_returns_parseable_json() -> None:
    parsed = json.loads(serialization.dumps(_Sample("y", _Nested(1), ())))
    assert parsed["name"] == "y"


@pytest.mark.parametrize(
    "argv",
    [
        ["--json", "system"],
        ["--json", "processes", "-n", "2"],
        ["--json", "network"],
        ["--json", "disk"],
        ["--json", "services"],
        ["--json", "whohas", "/nonexistent/xyz"],
    ],
)
def test_cli_json_output_is_valid_json(
    argv: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main(argv) == 0
    json.loads(capsys.readouterr().out)


def test_cli_json_kill_missing_pid_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["--json", "kill", "-12345"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["success"] is False


@pytest.mark.parametrize(
    "verbosity,level",
    [(0, logging.WARNING), (1, logging.INFO), (2, logging.DEBUG)],
)
def test_configure_logging_sets_level(verbosity: int, level: int) -> None:
    logger = configure_logging(verbosity)
    assert logger.name == LOGGER_NAME
    assert logger.level == level
    assert len(logger.handlers) == 1


def test_configure_logging_is_idempotent() -> None:
    configure_logging(1)
    logger = configure_logging(1)
    assert len(logger.handlers) == 1


def test_systemd_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    sample = "foo.service loaded active running Foo Daemon\nbar.service loaded inactive dead\n"

    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout=sample, stderr="")

    monkeypatch.setattr(services, "_run", fake_run)
    rows = services._list_services_systemd()
    assert [r.name for r in rows] == ["bar.service", "foo.service"]
    foo = next(r for r in rows if r.name == "foo.service")
    assert foo.status == "active/running"
    assert foo.description == "Foo Daemon"


def test_control_service_systemd_success(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(services, "_run", fake_run)
    result = services._control_service_systemd("foo", "start")
    assert result.success is True


def test_control_service_systemd_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, 1, stdout="", stderr="boom")

    monkeypatch.setattr(services, "_run", fake_run)
    result = services._control_service_systemd("foo", "stop")
    assert result.success is False
    assert "boom" in result.message
