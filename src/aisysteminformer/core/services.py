"""Cross-platform service inspection and control.

On Windows this uses :mod:`psutil`'s native service API. On Linux it shells out
to ``systemctl`` (read-only listing by default). All subprocess invocations pass
an explicit argument list (never ``shell=True``) and validate the action against
an allow-list, so there is no opportunity for command injection.
"""

from __future__ import annotations

import shutil
import subprocess  # noqa: S404 - usage is restricted to fixed, validated arg lists.
import sys
from dataclasses import dataclass

import psutil

#: Actions a caller is permitted to request. Anything else is rejected.
VALID_ACTIONS = ("start", "stop", "restart")


@dataclass(frozen=True)
class ServiceInfo:
    """A system service / unit."""

    name: str
    display_name: str
    status: str
    start_type: str
    pid: int | None
    description: str


@dataclass(frozen=True)
class ServiceActionResult:
    """Outcome of a service control request."""

    name: str
    action: str
    success: bool
    message: str


def services_supported() -> bool:
    """Return ``True`` if service inspection is available on this platform."""

    if sys.platform.startswith("win"):
        return hasattr(psutil, "win_service_iter")
    return shutil.which("systemctl") is not None


def list_services() -> list[ServiceInfo]:
    """Return the system's services, or an empty list if unsupported."""

    if sys.platform.startswith("win"):
        return _list_services_windows()
    if shutil.which("systemctl"):
        return _list_services_systemd()
    return []


def control_service(name: str, action: str) -> ServiceActionResult:
    """Start, stop or restart a service. Requires appropriate privileges."""

    if action not in VALID_ACTIONS:
        return ServiceActionResult(
            name, action, False, f"invalid action {action!r}; expected one of {VALID_ACTIONS}"
        )
    if sys.platform.startswith("win"):
        return _control_service_windows(name, action)
    if shutil.which("systemctl"):
        return _control_service_systemd(name, action)
    return ServiceActionResult(name, action, False, "service control unsupported on this platform")


# --- Windows -----------------------------------------------------------------


def _list_services_windows() -> list[ServiceInfo]:
    services: list[ServiceInfo] = []
    for svc in psutil.win_service_iter():  # type: ignore[attr-defined]
        try:
            info = svc.as_dict()
        except psutil.NoSuchProcess:
            continue
        services.append(
            ServiceInfo(
                name=info.get("name") or "",
                display_name=info.get("display_name") or "",
                status=info.get("status") or "",
                start_type=info.get("start_type") or "",
                pid=info.get("pid"),
                description=info.get("description") or "",
            )
        )
    services.sort(key=lambda s: s.name.lower())
    return services


def _control_service_windows(name: str, action: str) -> ServiceActionResult:
    # ``sc`` understands start/stop; restart is stop followed by start.
    sequence = ["stop", "start"] if action == "restart" else [action]
    for step in sequence:
        result = _run(["sc", step, name])
        if result.returncode != 0 and not (step == "stop" and action == "restart"):
            return ServiceActionResult(name, action, False, result.stderr.strip() or "sc failed")
    return ServiceActionResult(name, action, True, f"{action} requested for {name!r}")


# --- systemd -----------------------------------------------------------------


def _list_services_systemd() -> list[ServiceInfo]:
    result = _run(
        [
            "systemctl",
            "list-units",
            "--type=service",
            "--all",
            "--no-legend",
            "--no-pager",
            "--plain",
        ]
    )
    if result.returncode != 0:
        return []

    services: list[ServiceInfo] = []
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=4)
        if len(parts) < 4:
            continue
        unit, load_state, active_state, sub_state = parts[:4]
        description = parts[4] if len(parts) == 5 else ""
        services.append(
            ServiceInfo(
                name=unit,
                display_name=unit,
                status=f"{active_state}/{sub_state}",
                start_type=load_state,
                pid=None,
                description=description,
            )
        )
    services.sort(key=lambda s: s.name.lower())
    return services


def _control_service_systemd(name: str, action: str) -> ServiceActionResult:
    result = _run(["systemctl", action, name])
    if result.returncode == 0:
        return ServiceActionResult(name, action, True, f"{action} succeeded for {name!r}")
    message = result.stderr.strip() or f"systemctl {action} failed (exit {result.returncode})"
    return ServiceActionResult(name, action, False, message)


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    """Run a fixed command, capturing output and never using a shell."""

    return subprocess.run(  # noqa: S603 - args are fixed/validated, shell is never used.
        args,
        capture_output=True,
        text=True,
        check=False,
        timeout=15,
    )
