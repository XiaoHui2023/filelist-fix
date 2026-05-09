from __future__ import annotations

import logging

from rich.markup import escape

from api.events.filelist_build import OnSourceParsedAPI
from api.events.progress import OnProgressAPI


@OnProgressAPI.register
def sink_progress_visual(cb: OnProgressAPI) -> None:
    """Drive Rich Progress for phased and bounded steps."""
    ctx = cb.ctx
    prog = getattr(ctx, "rich_progress", None)
    tid = getattr(ctx, "progress_task_id", None)
    log = getattr(ctx, "logger", None)
    if log and log.isEnabledFor(logging.DEBUG):
        if cb.total is not None:
            log.debug("phase %s %s/%s", cb.phase, cb.current, cb.total)
        if cb.message:
            log.debug("%s", cb.message)
    if prog is None or tid is None:
        return
    phase_e = escape(cb.phase)
    msg_e = escape(cb.message) if cb.message else ""
    sep = " — " if msg_e else ""
    desc = f"[bold]{phase_e}[/bold]{sep}{msg_e}"
    if cb.total is not None:
        prog.update(tid, description=desc, total=cb.total, completed=min(cb.current, cb.total))
    else:
        prog.update(tid, description=desc, total=None, completed=0)


@OnSourceParsedAPI.register
def sink_source_parsed_progress(cb: OnSourceParsedAPI) -> None:
    """Update the progress line for each parsed source file."""
    ctx = cb.ctx
    prog = getattr(ctx, "rich_progress", None)
    tid = getattr(ctx, "progress_task_id", None)
    if prog is None or tid is None:
        return
    tag = "cache" if cb.cache_hit else "parse"
    msg = f"{escape(cb.path.name)} · {tag} · defs×{cb.defined_count} refs×{cb.referenced_count}"
    prog.update(
        tid,
        description=f"[bold]Parse & closure[/bold] — {msg}",
        total=None,
        completed=0,
    )
