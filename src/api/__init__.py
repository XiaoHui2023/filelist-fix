from __future__ import annotations

import importlib
import pkgutil
from typing import Any

from api.base import BaseAPI

_skipped = frozenset({"base"})


def _collect() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for _, name, ispkg in pkgutil.walk_packages(__path__, f"{__name__}."):
        if ispkg:
            continue
        seg = name.rsplit(".", 1)[-1]
        if seg in _skipped:
            continue
        mod = importlib.import_module(name)
        for key, val in vars(mod).items():
            if key.startswith("_"):
                continue
            if isinstance(val, type) and issubclass(val, BaseAPI) and val is not BaseAPI:
                out[key] = val
    return out


globals().update(_collect())
