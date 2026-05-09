from __future__ import annotations

import logging

from api.events.filelist_build import (
    OnModuleIndexInconsistentAPI,
    OnModuleResolveMissAPI,
)


@OnModuleResolveMissAPI.register
def sink_module_resolve_miss(cb: OnModuleResolveMissAPI) -> None:
    """Log unresolved module names."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("module not found, skipping: %s", cb.module_name)


@OnModuleIndexInconsistentAPI.register
def sink_module_index_inconsistent(cb: OnModuleIndexInconsistentAPI) -> None:
    """Log inconsistent module index state."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("internal index inconsistent, skipping module: %s", cb.module_name)
