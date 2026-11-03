from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any

from verilog_text.parse_budget import ParseBudget, active_budget


def note_cache_timing(ctx: Any, path: Any, elapsed: float) -> None:
    if not hasattr(ctx, "parse_timings"):
        ctx.parse_timings = []
    ctx.parse_timings.append({"path": str(path), "cache_hit": True, "status": "ok",
        "elapsed_seconds": elapsed, "stages": [{"stage": "cache", "path": str(path),
                                                 "elapsed_seconds": elapsed, "status": "ok"}]})
    log = getattr(ctx, "logger", None)
    if log is not None:
        log.info("parse stage=cache status=ok elapsed=%.6fs source=%s", elapsed, path)


@contextmanager
def monitor_source(path: Any, ctx: Any | None):
    """Record phase latency; the progress line already identifies the active file."""
    record: dict[str, Any] = {"path": str(path), "cache_hit": False, "stages": []}
    log = getattr(ctx, "logger", None)

    def observe(status: str, stage: str, source: str, elapsed: float) -> None:
        if log is not None:
            log.info("parse stage=%s status=%s elapsed=%.6fs source=%s", stage, status, elapsed, source)
        if status != "start":
            record["stages"].append({"stage": stage, "path": source,
                                     "elapsed_seconds": elapsed, "status": status})

    seconds = getattr(ctx, "parse_timeout", 30.0)
    budget = ParseBudget(str(path), seconds, observe)
    token = active_budget.set(budget)
    try:
        yield
        budget.check()
        record["status"] = "ok" if not getattr(ctx, "exit_code", None) else "failed"
    except BaseException as exc:
        record.update(status="failed", error=str(exc))
        raise
    finally:
        record["elapsed_seconds"] = perf_counter() - budget.started
        active_budget.reset(token)
        if ctx is not None:
            if not hasattr(ctx, "parse_timings"):
                ctx.parse_timings = []
            ctx.parse_timings.append(record)
        if log is not None:
            log.info("parse total status=%s elapsed=%.6fs source=%s", record.get("status"), record["elapsed_seconds"], path)
