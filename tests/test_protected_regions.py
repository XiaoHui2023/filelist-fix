from __future__ import annotations

from pathlib import Path

import impl  # noqa: F401

from core.source_flatten import extract_dependencies_from_file
from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan, strip_protected_regions


def test_strip_protected_removes_encrypted_block() -> None:
    src = """module top;
`protected
garbage module secret_core ();
`endprotected
  leaf u ();
endmodule
"""
    flat = strip_protected_regions(src)
    assert "secret_core" not in flat
    assert "garbage" not in flat
    assert "leaf u" in flat


def test_protect_endprotect_alias() -> None:
    src = """module m;
`protect
not_a_module fake ();
`endprotect
  sub s ();
endmodule
"""
    squ = squeeze_for_dependency_scan(src)
    r = scan_verilog_body(squ)
    assert "fake" not in r.referenced_modules
    assert "sub" in r.referenced_modules


def test_protected_stripped_before_flatten_and_scan(tmp_path: Path) -> None:
    src = tmp_path / "enc.sv"
    src.write_text(
        "module top;\n"
        "`protected\n"
        "module ghost;\n"
        "  phantom p1 ();\n"
        "endmodule\n"
        "`endprotected\n"
        "  real_child rc ();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    defs, refs, _ = extract_dependencies_from_file(src, [], {})
    assert defs == ["top"]
    assert "ghost" not in defs
    assert "phantom" not in refs
    assert "real_child" in refs
