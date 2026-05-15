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


def test_input_output_port_lines_stripped() -> None:
    src = """
module m (
  input wire clk,
  output logic q,
  inout tri1 pad
);
  leaf_mod u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "leaf_mod" in r.referenced_modules

def test_timescale_and_celldefine_lines_stripped() -> None:
    src = """
`timescale 1 ns / 1 ps
`celldefine
module leaf ();
endmodule
`endcelldefine
module top ();
  leaf u1 ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    assert "timescale" not in squ and "celldefine" not in squ
    r = scan_verilog_body(squ)
    assert r.defined_modules == ["leaf", "top"]
    assert r.referenced_modules == ["leaf"]


def test_task_body_not_scanned_for_instances() -> None:
    src = """
module m;
  task t;
    ghost_mod u ();
  endtask
  real_leaf v ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_mod" not in r.referenced_modules
    assert "real_leaf" in r.referenced_modules


def test_nested_tasks_stripped() -> None:
    src = """
module m;
  task outer;
    task inner;
      deep_ghost x ();
    endtask
  endtask
  ok_mod y ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "deep_ghost" not in r.referenced_modules
    assert "ok_mod" in r.referenced_modules


def test_extern_task_proto_skipped() -> None:
    src = """
extern task ext_t(
  input int x
);
module m;
  leaf u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    assert "ext_t" not in squ
    r = scan_verilog_body(squ)
    assert "leaf" in r.referenced_modules


def test_specify_block_not_scanned_for_instances() -> None:
    src = """
module m;
  specify
    ghost_mod u ();
  endspecify
  real_leaf v ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_mod" not in r.referenced_modules
    assert "real_leaf" in r.referenced_modules


def test_always_begin_end_hides_instance_like_text() -> None:
    src = """
module m;
  reg clk;
  always @(posedge clk) begin
    ghost_mod u ();
  end
  real_leaf v ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_mod" not in r.referenced_modules
    assert "real_leaf" in r.referenced_modules


def test_always_latch_block_stripped() -> None:
    src = """
module m;
  reg d, en;
  always_latch
    if (en) d <= 1'b0;
  ok_mod x ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ok_mod" in r.referenced_modules
    assert r.referenced_modules == ["ok_mod"]
