from __future__ import annotations

import importlib
import pkgutil


def _load_submodules() -> None:
    for _, name, ispkg in pkgutil.walk_packages(__path__, f"{__name__}."):
        if not ispkg:
            importlib.import_module(name)


_load_submodules()
