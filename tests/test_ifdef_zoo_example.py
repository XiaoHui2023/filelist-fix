"""`ifdef` / `ifndef` / `elsif` golden patterns in torture_ifdef_zoo.v."""

from pathlib import Path

from core.source_flatten import extract_dependencies_from_file
from runtime.context import AppContext


def test_ifdef_zoo_active_branches_with_prelude_like_defines(app_ctx: AppContext) -> None:
    root = Path(__file__).resolve().parents[1]
    rtl = root / "example" / "complex_rtl"
    zoo = rtl / "torture" / "torture_ifdef_zoo.v"
    incs = [rtl, rtl / "common", rtl / "hier", rtl / "pieces"]
    defines = {"WITH_DUAL": "1", "USE_CELLS": "1", "USE_CELLDEFINE": "1"}
    defs, refs, _ = extract_dependencies_from_file(zoo, incs, defines, ctx=app_ctx)
    assert defs == ["torture_ifdef_zoo"]
    assert set(refs) == {"torture_dep_a", "torture_dep_b", "ni_core_leaf"}
