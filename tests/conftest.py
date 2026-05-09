"""Shared pytest fixtures."""

from __future__ import annotations

import pytest

import impl  # noqa: F401 — side effect: register impl handlers

from runtime.context import AppContext


@pytest.fixture
def app_ctx() -> AppContext:
    """Minimal AppContext for code paths that use ctx.fire(...)."""
    return AppContext(logger=None, console=None)
