from __future__ import annotations

from verilog_text.scan import _parse_module_instantiation, scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan


def test_anonymous_and_named_instances() -> None:
    src = """
module holder ();
  torture_dep_a ();
  torture_dep_b u1 ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.defined_modules == ["holder"]
    assert set(r.referenced_modules) == {"torture_dep_a", "torture_dep_b"}


def test_generate_block_instance() -> None:
    src = """
module gen_holder ();
  genvar i;
  generate
    for (i = 0; i < 1; i = i + 1) begin : g
      torture_dep_a c ();
    end
  endgenerate
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "torture_dep_a" in r.referenced_modules


def test_bind_line() -> None:
    src = """
module mon ();
endmodule
bind top_chip torture_bind_mon mon_inst ();
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "mon" in r.defined_modules
    assert r.referenced_modules == ["torture_bind_mon"]


def test_timing_clutter_no_false_modules() -> None:
    src = """
module noise ();
  reg clk;
  initial #10 clk = 0;
  always @(posedge clk) begin end
  always_ff @(posedge clk) begin #1; end
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.referenced_modules == []


def test_instance_with_nested_hash_params() -> None:
    src = """
module m ();
  torture_param_leaf #(.W(4), .D(2)) u1 ();
  torture_param_leaf #(`M, `N) u2 ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.defined_modules == ["m"]
    assert set(r.referenced_modules) == {"torture_param_leaf"}


def test_bind_with_hash_params() -> None:
    src = """
module mon ();
endmodule
bind top_chip torture_param_leaf #(.W(1), .D(1)) mon_hp ();
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "mon" in r.defined_modules
    assert r.referenced_modules == ["torture_param_leaf"]


def test_assign_line_not_instance() -> None:
    src = """
module m ();
  assign x = y(z);
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "y" not in r.referenced_modules


def test_sized_literals_d_h_in_param_hash() -> None:
    """位宽进制字面量（如 5'ha、1'd1）中的单引号不得干扰 #() 括号配对。"""
    src = """
module m ();
  torture_param_leaf #(.W(5'ha), .D(1'd1)) u1 ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert r.defined_modules == ["m"]
    assert set(r.referenced_modules) == {"torture_param_leaf"}


def test_concat_and_replication_in_param_hash() -> None:
    """端口映射或参数里的 {a,b}、{N{…}} 不得打断例化行解析。"""
    src = """
module m ();
  torture_param_leaf #(.W({4'd1, 4'd0}), .D(2)) u_cat ();
  torture_param_leaf #(.W({4{1'b1}}), .D(1)) u_rep ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    inst_lines = [ln for ln in squ.splitlines() if "torture_param_leaf" in ln]
    assert len(inst_lines) == 2
    assert all(_parse_module_instantiation(ln, "m") == "torture_param_leaf" for ln in inst_lines)
    r = scan_verilog_body(squ)
    assert r.defined_modules == ["m"]
    assert r.referenced_modules == ["torture_param_leaf"]
