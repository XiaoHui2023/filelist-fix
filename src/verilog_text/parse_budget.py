from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from time import perf_counter
from typing import Callable


class ParseTimeout(TimeoutError):
    """The current source exceeded its dependency extraction budget."""


class ParseBudget:
    """Cooperative wall-clock deadline and phase observations for one source tree."""

    def __init__(self, path: str, seconds: float,
                 observer: Callable[[str, str, str, float], None]) -> None:
        self.path = path
        self.seconds = seconds
        self.started = perf_counter()
        self.current = "start"
        self.observer = observer

    def check(self) -> None:
        elapsed = perf_counter() - self.started
        if self.seconds and elapsed >= self.seconds:
            raise ParseTimeout(f"dependency extraction timeout: {self.path}; "
                               f"stage={self.current}; elapsed={elapsed:.3f}s; budget={self.seconds:g}s")


active_budget: ContextVar[ParseBudget | None] = ContextVar("dependency_parse_budget", default=None)


def check_parse_budget() -> None:
    budget = active_budget.get()
    if budget is not None:
        budget.check()


@contextmanager
def parse_stage(name: str, path: str = ""):
    budget = active_budget.get()
    if budget is None:
        yield
        return
    previous = budget.current
    budget.current = name
    started = perf_counter()
    status = "failed"
    budget.observer("start", name, path or budget.path, 0)
    try:
        budget.check()
        yield
        budget.check()
        status = "ok"
    finally:
        budget.observer(status, name, path or budget.path, perf_counter() - started)
        budget.current = previous
