from __future__ import annotations

from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan


def test_module_multiline_import_before_hash_params() -> None:
    """``module`` 名换行后 ``import``（可跨行）再 ``#(`` 的包名进入引用列表。"""
    src = """
module xxx
import  xxx_pkg::*,yyy_pkg::*;
#(
parameter int W = 1
) (
  input wire clk
);
  child_mod u ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "xxx_pkg" in r.referenced_modules
    assert "yyy_pkg" in r.referenced_modules
    assert "child_mod" in r.referenced_modules


def test_module_same_line_import_before_hash() -> None:
    src = """
module m import aa_pkg::*, bb_pkg::*; #(
  parameter X = 0
) ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "aa_pkg" in r.referenced_modules
    assert "bb_pkg" in r.referenced_modules


def test_package_def_and_inner_import() -> None:
    src = """
package p_inner;
endpackage
package p_outer;
  import p_inner::*;
  localparam int K = 1;
endpackage
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "p_inner" in r.defined_modules
    assert "p_outer" in r.defined_modules
    assert "p_inner" in r.referenced_modules
