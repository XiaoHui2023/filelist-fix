from __future__ import annotations

from verilog_text.scan import parse_instance_line_analysis, scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan
from verilog_text.ref_index import collect_module_ref_sites


def test_drive_strength_named_gate_not_in_referenced_modules() -> None:
    src = """
module top;
  wire y, a;
  buf (weak0, weak1) g1 (y, a);
  and (supply1, supply0) g_and (y, a, b);
  leaf_mod u_leaf ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "leaf_mod" in r.referenced_modules
    assert r.referenced_modules == ["leaf_mod"]

    t1, w1 = parse_instance_line_analysis("  buf (weak0, weak1) g1 (y, a);", "top")
    assert t1 == "buf" and "驱动强度" in w1
    t2, _ = parse_instance_line_analysis("  and (supply1, supply0) g_and (y, a, b);", "top")
    assert t2 == "and"


def test_drive_strength_anonymous_gate() -> None:
    src = """
module m;
  wire o, i;
  not (pull0, pull1) (o, i);
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.referenced_modules == []


def test_anonymous_gate_port_paren_unchanged() -> None:
    """无驱动强度时 ``buf (y, a);`` 仍按匿名门例化，不入 referenced_modules。"""
    src = """
module top;
  buf (y, a);
  xor (o, a, b);
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.referenced_modules == []


def test_ref_index_drive_strength_instance_name() -> None:
    src = """
module top;
  buf (weak0, weak1) g1 (y, a);
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    sites = [s for s in collect_module_ref_sites(squ) if s.referenced_module == "g1"]
    assert sites == []
