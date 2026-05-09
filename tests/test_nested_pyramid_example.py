"""多层 include / ifdef / generate 黄金样例的依赖解析。"""

from pathlib import Path

from core.source_flatten import extract_dependencies_from_file
from runtime.context import AppContext


def test_nested_pyramid_resolves_leaf_under_prelude_macros(app_ctx: AppContext) -> None:
    root = Path(__file__).resolve().parents[1]
    rtl = root / "example" / "complex_rtl"
    incs = [rtl, rtl / "common", rtl / "hier", rtl / "pieces"]
    p = rtl / "torture" / "nested" / "nested_pyramid.sv"
    defines = {"WITH_DUAL": "1", "USE_CELLS": "1", "USE_CELLDEFINE": "1"}
    defs, refs, _ = extract_dependencies_from_file(p, incs, defines, ctx=app_ctx)
    assert defs == ["nested_pyramid"]
    assert refs == ["ni_core_leaf"]
