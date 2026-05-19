"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

import impl  # noqa: F401 — side effect: register impl handlers

from runtime.context import AppContext


def bind_module_find(
    tools: object,
    resolver: Callable[[str], Path | None],
    *,
    track: list[str] | None = None,
) -> None:
    """为测试注入模块定位：``find_all`` / ``find_file`` 共用同一 resolver。"""
    def find_all(module: str, roots: list[Path]) -> list[Path]:
        if track is not None:
            track.append(module)
        hit = resolver(module)
        return [hit] if hit is not None else []

    tools.find_all = find_all
    tools.find_file = lambda m, r: resolver(m)


@pytest.fixture
def app_ctx() -> AppContext:
    """Minimal AppContext for code paths that use ctx.fire(...)."""
    return AppContext(logger=None, console=None)
