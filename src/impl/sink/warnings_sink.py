from __future__ import annotations

import logging
from rich.text import Text

from api.events.filelist_build import (
    OnBuildOrderInvalidAPI,
    OnModuleIndexInconsistentAPI,
    OnModuleResolveMissAPI,
)


@OnBuildOrderInvalidAPI.register
def sink_build_order_invalid(cb: OnBuildOrderInvalidAPI) -> None:
    log = getattr(cb.ctx, "logger", None)
    if log is not None:
        log.error("%s", cb.message)
    console = getattr(cb.ctx, "console", None)
    if console is not None:
        line = Text("Error", style="red")
        line.append(f": {cb.message}")
        console.print(line)
    cb.ctx.request_exit(1)


@OnModuleResolveMissAPI.register
def sink_module_resolve_miss(cb: OnModuleResolveMissAPI) -> None:
    """Report each unresolved definition before the closure is rejected."""
    log = getattr(cb.ctx, "logger", None)
    if log is not None:
        log.error('Not found module "%s"', cb.module_name)
    console = getattr(cb.ctx, "console", None)
    if console is not None:
        line = Text("Error", style="red")
        line.append(f': Not found module "{cb.module_name}"')
        console.print(line)


@OnModuleIndexInconsistentAPI.register
def sink_module_index_inconsistent(cb: OnModuleIndexInconsistentAPI) -> None:
    """Log inconsistent module index state."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("internal index inconsistent, skipping module: %s", cb.module_name)
