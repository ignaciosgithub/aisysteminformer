"""UI-agnostic system information collection layer.

Every module here returns plain dataclasses / primitives so the data can be
consumed equally well by the CLI, the TUI, or tests. No module in this package
imports a UI toolkit.
"""

from aisysteminformer.core import disk, files, formatting, network, processes, services, system

__all__ = [
    "disk",
    "files",
    "formatting",
    "network",
    "processes",
    "services",
    "system",
]
