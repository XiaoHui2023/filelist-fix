"""用户定义 primitive（UDP）：与 module 例化同形，须纳入定义集合与 rg 检索。"""

from __future__ import annotations

from pathlib import Path

import impl  # noqa: F401 — register sinks

import pytest

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication
from verilog_text.scan import scan_verilog_body


def test_scan_defined_modules_include_udp_primitive() -> None:
    src = (
        "primitive p_udp (o, i);\n"
        "  output o;\n"
        "  input i;\n"
        "  table\n"
        "    0 : 1;\n"
        "    1 : 0;\n"
        "  endtable\n"
        "endprimitive\n"
        "module m ();\n"
        "  wire o, i;\n"
        "  p_udp u1 (o, i);\n"
        "endmodule\n"
    )
    r = scan_verilog_body(src)
    assert sorted(r.defined_modules) == ["m", "p_udp"]
    assert r.referenced_modules == ["p_udp"]


def test_closure_udp_across_files_no_unresolved(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    from tools_bin_seed import project_has_tools_bin

    if not project_has_tools_bin(root):
        pytest.skip("工程 tools/bin 下缺少 rg/fd，请先运行 tools 下载脚本")

    rtl = tmp_path / "rtl2"
    rtl.mkdir()
    (rtl / "lib_udp.v").write_text(
        "primitive torture_udp_cell (q, a);\n"
        "  output q;\n"
        "  input a;\n"
        "  table\n"
        "    0 : 1;\n"
        "    1 : 0;\n"
        "  endtable\n"
        "endprimitive\n",
        encoding="utf-8",
    )
    (rtl / "top_udp_user.v").write_text(
        "module top_udp_user ();\n"
        "  wire q, a;\n"
        "  torture_udp_cell u1 (q, a);\n"
        "endmodule\n",
        encoding="utf-8",
    )

    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[rtl],
        top_modules=["top_udp_user"],
        prelude_paths=[],
        output_path=tmp_path / "udp_closure.f",
        save_path=None,
        ctx=ctx,
    )
    rb = app.run()
    assert rb.state.unresolved_modules == []
    names = {p.name for p in rb.ordered_paths}
    assert "lib_udp.v" in names
    assert "top_udp_user.v" in names
