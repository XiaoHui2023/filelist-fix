from __future__ import annotations

from pathlib import Path

import impl  # noqa: F401 — register sinks

from core.dependency_debug_dump import DependencyDebugDump
from core.source_flatten import extract_dependencies_from_file
from runtime.context import AppContext


def test_debug_dump_writes_pipeline_files(tmp_path: Path) -> None:
    src = tmp_path / "m.sv"
    src.write_text(
        "module m;\n"
        "  sub s1();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    dbg_root = tmp_path / "dbg"
    ctx = AppContext(logger=None, console=None, dependency_debug_dump=DependencyDebugDump(dbg_root))
    defs, refs, _ = extract_dependencies_from_file(src, [], {}, ctx=ctx)
    assert defs == ["m"]
    assert refs == ["sub"]
    subdirs = list((dbg_root / "by_file").iterdir())
    assert len(subdirs) == 1
    names = {p.name for p in subdirs[0].iterdir()}
    assert "00_source_path.txt" in names
    assert "01_joined.txt" in names
    assert "02_flatten_merged.txt" in names
    assert "03a_strip_comments.txt" in names
    assert "03b_drop_alwaysish.txt" in names
    assert "03c_squeeze_full.txt" in names
    assert "04_scan_result.txt" in names
    assert (dbg_root / "README.txt").is_file()
