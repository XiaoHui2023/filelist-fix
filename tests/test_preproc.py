from pathlib import Path

from core.filelist_prelude import load_prelude_files
from verilog_text.preproc import PreprocDirectiveParser
from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan


def test_ifdef_filters_inactive_branch() -> None:
    p = PreprocDirectiveParser({"A": "1"})
    text_lines = [
        "`ifdef A",
        "module m1();",
        "endmodule",
        "`else",
        "module m2();",
        "endmodule",
        "`endif",
    ]
    kept: list[str] = []
    for line in text_lines:
        if p.handle_directive_line(line):
            continue
        if p.line_is_active_source():
            kept.append(line)
    body = "\n".join(kept)
    scan = scan_verilog_body(squeeze_for_dependency_scan(body))
    assert "m1" in scan.defined_modules
    assert "m2" not in scan.defined_modules


def test_prelude_defines(tmp_path: Path) -> None:
    f = tmp_path / "p.f"
    f.write_text(f'+define+FOO=1\n+incdir+"{tmp_path}"\n', encoding="utf-8")
    out = load_prelude_files([f])
    assert "FOO" in out.defines


def test_prelude_relative_incdir(tmp_path: Path) -> None:
    here = tmp_path / "sub"
    here.mkdir()
    tgt = tmp_path / "inc_here"
    tgt.mkdir()
    prelude = here / "pre.f"
    prelude.write_text('+incdir+"../inc_here"\n', encoding="utf-8")
    out = load_prelude_files([prelude])
    assert len(out.incdirs) == 1
    assert out.incdirs[0] == tgt.resolve()
