from __future__ import annotations

import logging

from rich.markup import escape

from api.events.progress import OnProgressAPI


@OnProgressAPI.register
def sink_progress_visual(cb: OnProgressAPI) -> None:
    """alive-progress 条与调试日志中的阶段说明。"""
    ctx = cb.ctx
    bar = getattr(ctx, "alive_bar", None)
    log = getattr(ctx, "logger", None)
    if log and log.isEnabledFor(logging.DEBUG):
        if cb.total is not None:
            log.debug("阶段 %s %s/%s", cb.phase, cb.current, cb.total)
        if cb.message:
            log.debug("%s", cb.message)
    if bar is None:
        return
    text = cb.phase
    if cb.message:
        text = f"{cb.phase} — {cb.message}"
    bar.text(escape(text))
    if cb.current > 0:
        bar()
