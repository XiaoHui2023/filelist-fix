from __future__ import annotations

import logging

from rich.color import Color
from rich.color_triplet import ColorTriplet
from rich.style import Style
from rich.text import Text

from api.events.filelist_build import OnIncludeResolveMissAPI

_ERROR_STYLE = Style(color=Color.from_triplet(ColorTriplet(255, 80, 80)))


@OnIncludeResolveMissAPI.register
def sink_include_resolve_fatal(cb: OnIncludeResolveMissAPI) -> None:
    """无法解析的 `` `include``：立即在 stderr 打印 Error 并请求以非零状态结束。"""
    ctx = cb.ctx
    log = getattr(ctx, "logger", None)
    if log is not None:
        log.error(
            'Not found include "%s" in file "%s"',
            cb.include_spec,
            cb.from_file,
        )
    console = getattr(ctx, "console", None)
    if console is not None:
        line = Text()
        line.append("Error", style=_ERROR_STYLE)
        line.append(f': Not found include "{cb.include_spec}" in file "{cb.from_file}"')
        console.print(line)
    ctx.request_exit(1)
