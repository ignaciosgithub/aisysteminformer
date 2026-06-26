"""Centralised logging configuration.

Mutating, privileged operations (terminating a process, controlling a service)
emit structured ``INFO`` log records so there is an auditable trail of what the
tool did and why. By default logging is quiet (``WARNING`` and above); ``-v``
raises it to ``INFO`` and ``-vv`` to ``DEBUG``. Records go to ``stderr`` so they
never corrupt machine-readable ``--json`` output on ``stdout``.
"""

from __future__ import annotations

import logging
import sys

#: Root logger for the package; module loggers inherit from it.
LOGGER_NAME = "aisysteminformer"

_LEVELS = {0: logging.WARNING, 1: logging.INFO, 2: logging.DEBUG}


def configure_logging(verbosity: int = 0) -> logging.Logger:
    """Configure and return the package logger for the given ``verbosity``.

    ``verbosity`` is clamped to the supported range, so callers can pass a raw
    ``-v`` count without bounds-checking. Calling this more than once replaces
    the handler rather than stacking duplicates.
    """

    level = _LEVELS.get(max(0, min(verbosity, 2)), logging.DEBUG)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(level)

    for existing in list(logger.handlers):
        logger.removeHandler(existing)

    handler = logging.StreamHandler(stream=sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger
