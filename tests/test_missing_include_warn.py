from __future__ import annotations

import logging
from pathlib import Path

import impl  # noqa: F401 — register sinks

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_missing_include_recorded_once_per_file_and_spec(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "top.v").write_text(
        'module top();\n'
        '`include "absent.vh"\n'
        '`include "absent.vh"\n'
        "endmodule\n",
        encoding="utf-8",
    )
    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "out.f",
        save_path=None,
        ctx=ctx,
    )

    def fake_find(module: str, roots: object) -> Path | None:
        if module == "top":
            return src / "top.v"
        return None

    app._tools.find_file = fake_find
    app.run()
    assert ctx.include_resolve_miss_order == [("absent.vh", src / "top.v")]


def test_missing_include_warning_log_names_file_and_spec(caplog, tmp_path: Path) -> None:
    caplog.set_level(logging.WARNING)
    src = tmp_path / "src"
    src.mkdir()
    top = src / "top.v"
    top.write_text(
        'module top();\n`include "absent.vh"\nendmodule\n',
        encoding="utf-8",
    )
    log = logging.getLogger("missing_inc_warn_test")
    ctx = AppContext(logger=log, console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "out.f",
        save_path=None,
        ctx=ctx,
    )

    def fake_find(module: str, roots: object) -> Path | None:
        return top if module == "top" else None

    app._tools.find_file = fake_find
    app.run()
    joined = " ".join(r.getMessage() for r in caplog.records)
    assert 'Not found include "absent.vh"' in joined
    assert "in file" in joined
    assert str(top) in joined