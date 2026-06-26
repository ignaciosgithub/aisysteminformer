"""Find which processes are holding a file open.

This answers System Informer's classic "can't delete a file? find out who has it
open" question, in a cross-platform way via :mod:`psutil`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import psutil


@dataclass(frozen=True)
class FileHolder:
    """A process that references a given path, and how it references it."""

    pid: int
    process_name: str
    path: str
    # One of: "open_file", "cwd", "exe", "memory_map".
    reference: str


def _normalise(path: str) -> str:
    """Return an absolute, symlink-resolved path for robust comparison."""

    return os.path.realpath(os.path.abspath(os.path.expanduser(path)))


def find_processes_using_path(target: str) -> list[FileHolder]:
    """Return every process that has ``target`` open or otherwise references it.

    Matching covers open file descriptors, the working directory, the
    executable image and memory-mapped files. Accessing other users' handles
    usually requires elevated privileges; unreadable processes are skipped, so
    results may be incomplete when run unprivileged.
    """

    wanted = _normalise(target)
    holders: list[FileHolder] = []

    for proc in psutil.process_iter(["pid", "name"]):
        pid = proc.info["pid"]
        name = proc.info.get("name") or ""
        try:
            with proc.oneshot():
                _check_open_files(proc, wanted, pid, name, holders)
                _check_attr_path(proc.cwd, wanted, pid, name, "cwd", holders)
                _check_attr_path(proc.exe, wanted, pid, name, "exe", holders)
                _check_memory_maps(proc, wanted, pid, name, holders)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return holders


def _check_open_files(
    proc: psutil.Process, wanted: str, pid: int, name: str, out: list[FileHolder]
) -> None:
    try:
        for open_file in proc.open_files():
            if _normalise(open_file.path) == wanted:
                out.append(FileHolder(pid, name, open_file.path, "open_file"))
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass


def _check_attr_path(
    getter: object, wanted: str, pid: int, name: str, reference: str, out: list[FileHolder]
) -> None:
    try:
        value = getter() if callable(getter) else None
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return
    if value and _normalise(value) == wanted:
        out.append(FileHolder(pid, name, value, reference))


def _check_memory_maps(
    proc: psutil.Process, wanted: str, pid: int, name: str, out: list[FileHolder]
) -> None:
    try:
        for mmap in proc.memory_maps():
            mapped = getattr(mmap, "path", "") or ""
            if mapped and os.path.isabs(mapped) and _normalise(mapped) == wanted:
                out.append(FileHolder(pid, name, mapped, "memory_map"))
    except (psutil.AccessDenied, psutil.NoSuchProcess, NotImplementedError, OSError):
        pass
