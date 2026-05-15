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


def test_multiline_assign_stripped_until_semicolon() -> None:
    src = """
module m;
  assign xxx = 1'b0 |
          1'b1 |
          1'b0;
  dep_mod u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "dep_mod" in r.referenced_modules


def test_leading_parameterized_instance_body_not_stripped_as_module_header() -> None:
    """module 体首 ``#(…)`` 若为例化参数表（后接模块名而非端口表 ``(`` / ``;``），不得整段剥掉。"""
    src = """
module top ();
  #(.W(1)) sub i ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert r.defined_modules == ["top"]
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


def test_always_begin_inner_case_endcase_nested() -> None:
    """always → begin → case → begin/end 嵌套时整块丢弃，不外泄伪例化。"""
    src = """
module m;
  reg clk;
  always @(posedge clk) begin
    case (1'b1)
      1'b1: begin
        ghost_in_case g ();
      end
      default: begin
      end
    endcase
  end
  real_mod u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_in_case" not in r.referenced_modules
    assert "real_mod" in r.referenced_modules


def test_always_ff_case_without_begin_on_first_line() -> None:
    """首行无 begin、第二行起 case…endcase 时仍能吞到 endcase 之后。"""
    src = """
module m;
  reg clk;
  always_ff @(posedge clk)
  case (clk)
    1'b0: ;
    default: ;
  endcase
  leaf_mod x ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "leaf_mod" in r.referenced_modules


def test_generate_nested_case_if_begin_stripped() -> None:
    """generate 内嵌 case / if-else / begin-end 仍整段去掉，不外扫例化。"""
    src = """
module m;
  generate
    case (1)
      1'b1: begin
        if (1) begin
          ghost_inst gi ();
        end else if (0) begin
        end else begin
        end
      end
      default: begin
      end
    endcase
  endgenerate
  good_mod gm ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_inst" not in r.referenced_modules
    assert "good_mod" in r.referenced_modules


def test_nested_generate_stripped() -> None:
    src = """
module m;
  generate
    generate
      deep_ghost dg ();
    endgenerate
  endgenerate
  tail_mod t ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "deep_ghost" not in r.referenced_modules
    assert "tail_mod" in r.referenced_modules


def test_labelled_generate_stripped() -> None:
    src = """
module m;
  outer_l : generate
    ghost_a a ();
  endgenerate
  good_b b ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "ghost_a" not in r.referenced_modules
    assert "good_b" in r.referenced_modules


def test_multiline_localparam_stripped() -> None:
    src = """
module m;
  localparam  xxx = 1'd1,
                    xxy = 2'd2,
                   xxz = 3'd1;
  leaf_mod u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "xxx" not in r.referenced_modules
    assert "xxy" not in r.referenced_modules
    assert "xxz" not in r.referenced_modules
    assert "leaf_mod" in r.referenced_modules
