from __future__ import annotations

import logging

from rich.color import Color
from rich.color_triplet import ColorTriplet
from rich.style import Style
from rich.text import Text

from api.events.filelist_build import OnIncludeResolveMissAPI

_ERROR_STYLE = Style(color=Color.from_triplet(ColorTriplet(255, 80, 80)))


def _format_include_list(specs: list[str]) -> str:
    return ", ".join(f'"{s}"' for s in specs)


@OnIncludeResolveMissAPI.register
def sink_include_resolve_fatal(cb: OnIncludeResolveMissAPI) -> None:
    """无法解析的 `` `include``：按源文件合并为一条 Error 并请求以非零状态结束。"""
    ctx = cb.ctx
    quoted = _format_include_list(cb.include_specs)
    log = getattr(ctx, "logger", None)
    if log is not None:
        log.error('Not found include %s in file "%s"', quoted, cb.from_file)
    console = getattr(ctx, "console", None)
    if console is not None:
        line = Text()
        line.append("Error", style=_ERROR_STYLE)
        line.append(f": Not found include {quoted} in file \"{cb.from_file}\"")
        console.print(line)
    ctx.request_exit(1)
