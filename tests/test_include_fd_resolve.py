from __future__ import annotations

import logging
from pathlib import Path

import impl  # noqa: F401 — register sinks

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_include_fd_adds_incdir_above_source_file(tmp_path: Path) -> None:
    src = tmp_path / "src"
    inc_dir = src / "nested" / "hdr"
    inc_dir.mkdir(parents=True)
    hdr = inc_dir / "types.vh"
    hdr.write_text("`define T 1\n", encoding="utf-8")
    top = src / "top.v"
    top.write_text(
        'module top();\n`include "types.vh"\nendmodule\n',
        encoding="utf-8",
    )
    out = tmp_path / "out.f"
    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=out,
        save_path=None,
        ctx=ctx,
    )

    def fake_find(module: str, roots: object) -> Path | None:
        return top if module == "top" else None

    app._tools.find_file = fake_find
    app._tools.find_all = lambda m, r: [top] if m == "top" else []
    app._tools.fd_search_by_filename = lambda name, roots, excl=None: (
        [hdr] if name == "types.vh" else []
    )

    rb = app.run()
    assert rb is not None
    assert ctx.exit_code is None
    text = out.read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if ln.strip()]
    top_line = next(ln for ln in lines if ln.endswith("top.v"))
    idx = lines.index(top_line)
    assert idx > 0
    assert lines[idx - 1].startswith("+incdir+")
    assert "nested" in lines[idx - 1] or "hdr" in lines[idx - 1]


def test_include_fd_ambiguous_lists_paths_and_exits(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.ERROR)
    src = tmp_path / "src"
    a = src / "a"
    b = src / "b"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    fa = a / "dup.vh"
    fb = b / "dup.vh"
    fa.write_text("`define A 1\n", encoding="utf-8")
    fb.write_text("`define B 2\n", encoding="utf-8")
    top = src / "top.v"
    top.write_text('module top();\n`include "dup.vh"\nendmodule\n', encoding="utf-8")
    ctx = AppContext(logger=logging.getLogger("inc_amb"), console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "out.f",
        save_path=None,
        ctx=ctx,
    )

    app._tools.find_file = lambda m, r: top if m == "top" else None
    app._tools.find_all = lambda m, r: [top] if m == "top" else []
    app._tools.fd_search_by_filename = lambda name, roots, excl=None: (
        [fa, fb] if name == "dup.vh" else []
    )

    assert app.run() is None
    assert ctx.exit_code == 1
    msg = caplog.text
    assert "Ambiguous include" in msg
    assert str(fa) in msg and str(fb) in msg
    assert "--exclude" in msg


def test_module_duplicate_fd_hits_exit(tmp_path: Path, caplog) -> None:
    caplog.set_level(logging.ERROR)
    src = tmp_path / "src"
    f1 = src / "child_a.sv"
    f2 = src / "child_b.sv"
    src.mkdir(parents=True)
    f1.write_text("module child();\nendmodule\n", encoding="utf-8")
    f2.write_text("module child();\nendmodule\n", encoding="utf-8")
    top = src / "top.sv"
    top.write_text("module top();\n  child u();\nendmodule\n", encoding="utf-8")
    ctx = AppContext(logger=logging.getLogger("mod_dup"), console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "out.f",
        save_path=None,
        ctx=ctx,
    )

    def find_all(mod: str, roots: object) -> list[Path]:
        if mod == "top":
            return [top]
        if mod == "child":
            return [f1, f2]
        return []

    app._tools.find_all = find_all
    app._tools.find_file = lambda m, r: find_all(m, r)[0] if len(find_all(m, r)) == 1 else None

    assert app.run() is None
    assert ctx.exit_code == 1
    assert "Duplicate definition" in caplog.text
    assert str(f1) in caplog.text and str(f2) in caplog.text
