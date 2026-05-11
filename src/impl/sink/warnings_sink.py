from __future__ import annotations

import logging

from api.events.filelist_build import (
    OnModuleIndexInconsistentAPI,
    OnModuleResolveMissAPI,
)


@OnModuleResolveMissAPI.register
def sink_module_resolve_miss(cb: OnModuleResolveMissAPI) -> None:
    """Miss details at DEBUG; run-end summary on stderr and WARNING in log when ``-l`` is set."""
    log = getattr(cb.ctx, "logger", None)
    if log is not None and log.isEnabledFor(logging.DEBUG):
        log.debug("module resolve miss (run-end summary on stderr): %s", cb.module_name)


@OnModuleIndexInconsistentAPI.register
def sink_module_index_inconsistent(cb: OnModuleIndexInconsistentAPI) -> None:
    """Log inconsistent module index state."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("internal index inconsistent, skipping module: %s", cb.module_name)
