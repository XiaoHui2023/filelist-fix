from __future__ import annotations

import logging

from api.events.filelist_build import (
    OnModuleIndexInconsistentAPI,
    OnModuleResolveMissAPI,
)


@OnModuleResolveMissAPI.register
def sink_module_resolve_miss(cb: OnModuleResolveMissAPI) -> None:
    """Emit a WARNING when a logger is present so ``-l`` files see misses next to DEBUG context."""
    log = getattr(cb.ctx, "logger", None)
    if log is None:
        return
    log.warning('Not found module "%s"', cb.module_name)


@OnModuleIndexInconsistentAPI.register
def sink_module_index_inconsistent(cb: OnModuleIndexInconsistentAPI) -> None:
    """Log inconsistent module index state."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("internal index inconsistent, skipping module: %s", cb.module_name)
