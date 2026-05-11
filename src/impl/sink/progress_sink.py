from __future__ import annotations

import logging

from rich.markup import escape

from api.events.filelist_build import OnSourceParsedAPI
from api.events.progress import OnProgressAPI


@OnProgressAPI.register
def sink_progress_visual(cb: OnProgressAPI) -> None:
    """Drive Rich Progress; prefer short dynamic lines from ``message``."""
    ctx = cb.ctx
    prog = getattr(ctx, "rich_progress", None)
    tid = getattr(ctx, "progress_task_id", None)
    log = getattr(ctx, "logger", None)
    if log is not None and log.isEnabledFor(logging.DEBUG):
        parts = [p for p in (cb.phase, cb.message) if p]
        extra = f"{cb.current}/{cb.total}" if cb.total is not None else ""
        log.debug("progress %s %s", " · ".join(parts) if parts else "(tick)", extra)

    if prog is None or tid is None:
        return

    if cb.message:
        desc = f"[bold]{escape(cb.message)}[/bold]"
    elif cb.phase:
        desc = escape(cb.phase)
    else:
        desc = "[dim]…[/dim]"

    if cb.total is not None:
        prog.update(
            tid,
            description=desc,
            total=cb.total,
            completed=min(cb.current, cb.total),
        )
    else:
        prog.update(tid, description=desc, total=None, completed=0)


@OnSourceParsedAPI.register
def sink_source_parsed_progress(cb: OnSourceParsedAPI) -> None:
    """Refresh the progress line from the last parsed file; keep closure ``total``/``completed``."""
    ctx = cb.ctx
    prog = getattr(ctx, "rich_progress", None)
    tid = getattr(ctx, "progress_task_id", None)
    if prog is None or tid is None:
        return
    try:
        task = prog.tasks[tid]
    except (IndexError, TypeError):
        task = None
    tag = "cache" if cb.cache_hit else "parse"
    msg = (
        f"[cyan]{escape(cb.path.name)}[/cyan] · [yellow]{tag}[/yellow] · "
        f"[green]{cb.defined_count}[/green] def · [blue]{cb.referenced_count}[/blue] ref"
    )
    if task is not None and task.total is not None:
        prog.update(
            tid,
            description=msg,
            total=task.total,
            completed=task.completed,
        )
    else:
        prog.update(tid, description=msg, total=None, completed=0)
