from __future__ import annotations

import math

import pytest

from aisysteminformer.core import formatting


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.0 KiB"),
        (1536, "1.5 KiB"),
        (1024**2, "1.0 MiB"),
        (1024**3, "1.0 GiB"),
        (-2048, "-2.0 KiB"),
    ],
)
def test_human_bytes(value: float, expected: str) -> None:
    assert formatting.human_bytes(value) == expected


def test_human_bytes_nan() -> None:
    assert formatting.human_bytes(math.nan) == "n/a"


def test_human_rate() -> None:
    assert formatting.human_rate(2048) == "2.0 KiB/s"


@pytest.mark.parametrize(
    ("seconds", "expected"),
    [
        (0, "00:00:00"),
        (59, "00:00:59"),
        (3661, "01:01:01"),
        (90061, "1d 01:01:01"),
        (-5, "n/a"),
    ],
)
def test_human_duration(seconds: float, expected: str) -> None:
    assert formatting.human_duration(seconds) == expected


def test_human_percent() -> None:
    assert formatting.human_percent(12.345) == "12.3%"
    assert formatting.human_percent(math.nan) == "n/a"


@pytest.mark.parametrize(
    ("text", "length", "expected"),
    [
        ("hello", 10, "hello"),
        ("hello world", 5, "hell\u2026"),
        ("hi", 0, ""),
        ("abc", 1, "a"),
    ],
)
def test_truncate(text: str, length: int, expected: str) -> None:
    assert formatting.truncate(text, length) == expected


def test_format_timestamp_invalid() -> None:
    assert formatting.format_timestamp(0) == "n/a"
    assert formatting.format_timestamp(-1) == "n/a"
