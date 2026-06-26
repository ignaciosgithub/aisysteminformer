"""Convert core dataclasses into JSON-serialisable primitives.

The CLI exposes a ``--json`` mode so its output can be consumed by other tools
(monitoring pipelines, tests, audits) without scraping human-formatted tables.
Keeping the conversion in one pure, well-tested place means every command emits
a consistent, predictable shape.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any


def to_jsonable(value: Any) -> Any:
    """Recursively convert dataclasses, tuples and mappings into JSON primitives.

    Dataclasses become dicts, sequences become lists and everything else is
    returned unchanged (``str``/``int``/``float``/``bool``/``None``). The result
    is guaranteed to be accepted by :func:`json.dumps`.
    """

    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]
    return value


def dumps(value: Any, *, indent: int | None = 2) -> str:
    """Serialise ``value`` (including dataclasses) to a JSON string."""

    return json.dumps(to_jsonable(value), indent=indent, sort_keys=False)
