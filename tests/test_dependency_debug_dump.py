from __future__ import annotations

from pathlib import Path

import impl  # noqa: F401 — register sinks

from core.dependency_debug_dump import DependencyDebugDump
from core.source_flatten import extract_dependencies_from_file
from core.path_logical import logical_abs
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
    assert "03c_strip_decl_noise.txt" in names
    assert "03d0_pre_strip_module_ports.txt" in names
    assert "03d_strip_module_ports.txt" in names
    assert "03e_scan_input.txt" in names
    assert "05_instance_scan_trace.txt" in names
    assert "04_scan_result.txt" in names
    assert (dbg_root / "README.txt").is_file()
    assert not (dbg_root / "last_run.txt").exists()
    assert subdirs[0].name == "m"
    ddir = subdirs[0]
    assert (
        ddir / "03c_strip_decl_noise.txt"
    ).read_text(encoding="utf-8") == (ddir / "03d0_pre_strip_module_ports.txt").read_text(
        encoding="utf-8"
    )
    trace = (ddir / "05_instance_scan_trace.txt").read_text(encoding="utf-8")
    assert "MATCH" in trace
    assert "sub" in trace


def test_debug_dump_clears_by_file_on_new_session(tmp_path: Path) -> None:
    dbg_root = tmp_path / "dbg_wipe"
    a = tmp_path / "only_a.sv"
    a.write_text("module only_a;\nendmodule\n", encoding="utf-8")
    ctx_a = AppContext(logger=None, console=None, dependency_debug_dump=DependencyDebugDump(dbg_root))
    extract_dependencies_from_file(a, [], {}, ctx=ctx_a)
    assert len(list((dbg_root / "by_file").iterdir())) == 1

    b = tmp_path / "only_b.sv"
    b.write_text("module only_b;\nendmodule\n", encoding="utf-8")
    ctx_b = AppContext(logger=None, console=None, dependency_debug_dump=DependencyDebugDump(dbg_root))
    extract_dependencies_from_file(b, [], {}, ctx=ctx_b)
    subs = list((dbg_root / "by_file").iterdir())
    assert len(subs) == 1
    assert str(logical_abs(b)) in (subs[0] / "00_source_path.txt").read_text(encoding="utf-8")


def test_debug_dump_removes_legacy_last_run(tmp_path: Path) -> None:
    dbg_root = tmp_path / "dbg3"
    dbg_root.mkdir(parents=True)
    stale = dbg_root / "last_run.txt"
    stale.write_text("utc_start: old\n", encoding="utf-8")
    DependencyDebugDump(dbg_root)
    assert not stale.exists()


def test_debug_dump_same_basename_uses_hash_when_colliding(tmp_path: Path) -> None:
    d1 = tmp_path / "a"
    d2 = tmp_path / "b"
    d1.mkdir()
    d2.mkdir()
    f1 = d1 / "dup.sv"
    f2 = d2 / "dup.sv"
    f1.write_text("module dup;\nendmodule\n", encoding="utf-8")
    f2.write_text("module dup;\nendmodule\n", encoding="utf-8")
    dbg_root = tmp_path / "dbg_dup"
    ctx = AppContext(logger=None, console=None, dependency_debug_dump=DependencyDebugDump(dbg_root))
    extract_dependencies_from_file(f1, [], {}, ctx=ctx)
    extract_dependencies_from_file(f2, [], {}, ctx=ctx)
    names = sorted(p.name for p in (dbg_root / "by_file").iterdir())
    assert len(names) == 2
    assert all(n.startswith("dup_") for n in names)
    suffixes = [n.rsplit("_", 1)[-1] for n in names]
    assert len(suffixes[0]) == 16 and set(suffixes[0]) <= set("0123456789abcdef")
    assert suffixes[0] != suffixes[1]


def test_debug_dump_00_source_path_overwrites_stale(tmp_path: Path) -> None:
    src = tmp_path / "m.sv"
    src.write_text("module m;\nendmodule\n", encoding="utf-8")
    dbg_root = tmp_path / "dbg2"
    ctx = AppContext(logger=None, console=None, dependency_debug_dump=DependencyDebugDump(dbg_root))
    extract_dependencies_from_file(src, [], {}, ctx=ctx)
    sub = next((dbg_root / "by_file").iterdir())
    (sub / "00_source_path.txt").write_text("stale-path\n", encoding="utf-8")
    extract_dependencies_from_file(src, [], {}, ctx=ctx)
    assert (sub / "00_source_path.txt").read_text(encoding="utf-8").strip() == str(logical_abs(src))
