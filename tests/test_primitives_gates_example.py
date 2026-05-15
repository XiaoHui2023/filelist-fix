"""Gate primitives are parsed as instantiations (trace / port skeleton) but are not closure dependencies."""

from pathlib import Path

from verilog_text.scan_trace import build_instance_scan_trace
from verilog_text.squeeze import squeeze_for_dependency_scan

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
    squ = squeeze_for_dependency_scan(p.read_text(encoding="utf-8"))
    trace = build_instance_scan_trace(squ)
    assert "内建门" in trace
