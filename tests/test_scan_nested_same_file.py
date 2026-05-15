from __future__ import annotations

from pathlib import Path

from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan

from core.source_flatten import extract_dependencies_from_file


def test_nested_modules_same_file_inner_ref_in_closure() -> None:
    """嵌套 module 时 inner 的例化仍应扫到，且 inner 与 outer 同文件时不应误报未找到。"""
    src = """
module outer ();
  module inner ();
    leaf_mod u1 ();
  endmodule
  inner i1 ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "outer" in r.defined_modules and "inner" in r.defined_modules
    assert "inner" in r.referenced_modules
    assert "leaf_mod" in r.referenced_modules


def test_sibling_modules_same_file_cross_ref() -> None:
    """同文件并列 module：A 例化 B，两者均须出现在 defined_modules。"""
    src = """
module mod_b ();
endmodule
module mod_a ();
  mod_b u ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert r.defined_modules == ["mod_a", "mod_b"]
    assert r.referenced_modules == ["mod_b"]


def test_uppercase_gate_primitive_not_in_referenced_modules(tmp_path: Path) -> None:
    """门原语类型名大写时不应进入 referenced_modules（避免 fd/rg 误找模块）。"""
    v = tmp_path / "gates.v"
    v.write_text(
        "module m();\n"
        "  wire a, b, y;\n"
        "  NOT n1 (y, a);\n"
        "  AND a1 (y, a, b);\n"
        "endmodule\n",
        encoding="utf-8",
    )
    defs, refs, _ = extract_dependencies_from_file(v, [tmp_path], {}, ctx=None)
    assert defs == ["m"]
    assert refs == []
