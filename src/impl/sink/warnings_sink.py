from __future__ import annotations

import logging

from api.events.filelist_build import (
    OnIncludeResolveMissAPI,
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


@OnIncludeResolveMissAPI.register
def sink_include_resolve_miss(cb: OnIncludeResolveMissAPI) -> None:
    """Emit a WARNING when an `` `include`` file cannot be resolved (same channel as module misses)."""
    log = getattr(cb.ctx, "logger", None)
    if log is None:
        return
    log.warning(
        'Not found include "%s" in file "%s"',
        cb.include_spec,
        cb.from_file,
    )


@OnModuleIndexInconsistentAPI.register
def sink_module_index_inconsistent(cb: OnModuleIndexInconsistentAPI) -> None:
    """Log inconsistent module index state."""
    log = getattr(cb.ctx, "logger", None) or logging.getLogger(__name__)
    log.warning("internal index inconsistent, skipping module: %s", cb.module_name)
