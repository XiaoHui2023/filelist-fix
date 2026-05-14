from __future__ import annotations

from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan


def test_squeeze_strips_ports_then_finds_instance() -> None:
    src = """
module foo (input wire clk, output logic x);
  dep_mod u1 ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert r.defined_modules == ["foo"]
    assert "dep_mod" in r.referenced_modules


def test_assign_line_noise_stripped() -> None:
    src = """
module m;
  assign a = y(z);
  sub s ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "y" not in r.referenced_modules
    assert "sub" in r.referenced_modules
