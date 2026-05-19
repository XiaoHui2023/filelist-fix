from __future__ import annotations

from rich.color import Color
from rich.color_triplet import ColorTriplet
from rich.style import Style
from rich.text import Text

from api.events.filelist_build import (
    OnIncludeResolveAmbiguousAPI,
    OnModuleResolveDuplicateAPI,
)

_ERROR_STYLE = Style(color=Color.from_triplet(ColorTriplet(255, 80, 80)))


def _format_path_list(paths: list[object]) -> str:
    return "\n  ".join(str(p) for p in paths)


def _emit_fatal(ctx: object, log_msg: str, console_body: str) -> None:
    log = getattr(ctx, "logger", None)
    if log is not None:
        log.error(log_msg)
    console = getattr(ctx, "console", None)
    if console is not None:
        line = Text()
        line.append("Error", style=_ERROR_STYLE)
        line.append(f": {console_body}")
        console.print(line)
    getattr(ctx, "request_exit", lambda _c: None)(1)


@OnIncludeResolveAmbiguousAPI.register
def sink_include_resolve_ambiguous(cb: OnIncludeResolveAmbiguousAPI) -> None:
    """同名 include 目标在源树中命中多个文件：列出路径并请求非零退出。"""
    paths = cb.candidate_paths
    log_msg = (
        'Ambiguous include "%s" in file "%s"; multiple matches (use --exclude):\n  %s'
        % (cb.include_spec, cb.from_file, _format_path_list(paths))
    )
    body = (
        f'Ambiguous include "{cb.include_spec}" in file "{cb.from_file}"; '
        f"multiple matches (use --exclude):\n  {_format_path_list(paths)}"
    )
    _emit_fatal(cb.ctx, log_msg, body)


@OnModuleResolveDuplicateAPI.register
def sink_module_resolve_duplicate(cb: OnModuleResolveDuplicateAPI) -> None:
    """同一模块名对应多个定义文件：列出路径并请求非零退出。"""
    paths = cb.candidate_paths
    log_msg = (
        'Duplicate definition for module "%s" (use --exclude):\n  %s'
        % (cb.module_name, _format_path_list(paths))
    )
    body = (
        f'Duplicate definition for module "{cb.module_name}" '
        f"(use --exclude):\n  {_format_path_list(paths)}"
    )
    _emit_fatal(cb.ctx, log_msg, body)
