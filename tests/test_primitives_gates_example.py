"""Gate primitives in golden RTL must not become module dependencies."""

from pathlib import Path

from core.source_flatten import extract_dependencies_from_file
from runtime.context import AppContext


def test_primitives_gates_only_refs_user_module(app_ctx: AppContext) -> None:
    root = Path(__file__).resolve().parents[1]
    rtl = root / "example" / "complex_rtl"
    p = rtl / "torture" / "torture_primitives_gates.v"
    incs = [rtl, rtl / "common", rtl / "hier", rtl / "pieces"]
    defs, refs, _ = extract_dependencies_from_file(p, incs, {}, ctx=app_ctx)
    assert defs == ["torture_primitives_gates"]
    assert refs == ["torture_dep_a"]
