from __future__ import annotations

from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import drop_alwaysish_blocks, squeeze_for_dependency_scan


def test_typedef_struct_multiline_ignores_inner_instance_like_syntax() -> None:
    src = """
module m ();
typedef struct packed {
  BadMod x ();
} st_t;
RealChild rc ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "BadMod" not in r.referenced_modules
    assert "RealChild" in r.referenced_modules


def test_typedef_enum_multiline_ignores_inner_instance_like_syntax() -> None:
    src = """
module m ();
typedef enum int {
  IDLE,
  GhostMod y ()
} state_e;
RealChild rc ();
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "GhostMod" not in r.referenced_modules
    assert "RealChild" in r.referenced_modules


def test_always_split_across_lines_still_dropped() -> None:
    src = """
module m ();
always
_comb
begin
  InnerMod u ();
end
endmodule
"""
    mid = drop_alwaysish_blocks(src)
    assert "InnerMod" not in mid
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "InnerMod" not in r.referenced_modules


def test_always_ff_split_across_lines_still_dropped() -> None:
    src = """
module m ();
always
_ff @(posedge clk) begin
  InnerMod u ();
end
endmodule
"""
    mid = drop_alwaysish_blocks(src)
    assert "InnerMod" not in mid


def test_begin_colon_label_same_line_instance() -> None:
    src = """
module m ();
begin : blk_name RealMod u ();
end
endmodule
"""
    r = scan_verilog_body(squeeze_for_dependency_scan(src))
    assert "RealMod" in r.referenced_modules
