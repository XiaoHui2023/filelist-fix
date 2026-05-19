from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_save_reuses_cache_when_prelude_only_adds_incdir(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    inc = tmp_path / "inc"
    rtl.mkdir()
    inc.mkdir()
    (inc / "hdr.vh").write_text("`define HDR 1\n", encoding="utf-8")
    top = rtl / "top.v"
    top.write_text(
        'module top();\n`include "hdr.vh"\nendmodule\n',
        encoding="utf-8",
    )
    pre_base = tmp_path / "pre0.f"
    pre_base.write_text(
        f"+define+K=1\n+incdir+{inc.as_posix()}\n",
        encoding="utf-8",
    )
    extra_inc = tmp_path / "extra_inc"
    extra_inc.mkdir()
    pre_extra = tmp_path / "pre1.f"
    pre_extra.write_text(
        f"+define+K=1\n+incdir+{inc.as_posix()}\n+incdir+{extra_inc.as_posix()}\n",
        encoding="utf-8",
    )
    db = tmp_path / "cache.db"
    out = tmp_path / "out.f"
    hits = {"top": top}
    find_mock = MagicMock(side_effect=lambda m, *_: hits.get(m))

    def run_with_prelude(pre: Path) -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[rtl],
            top_modules=["top"],
            prelude_paths=[pre],
            output_path=out,
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = find_mock
        app.run()
        assert ctx.exit_code is None

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:
        ext.side_effect = lambda path, *_a, **_k: (["top"], [], [])
        run_with_prelude(pre_base)
        first_calls = ext.call_count
        run_with_prelude(pre_extra)
        second_calls = ext.call_count
    assert first_calls >= 1
    assert second_calls == first_calls


def test_save_invalidates_when_define_changes(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl2"
    rtl.mkdir()
    top = rtl / "top.v"
    top.write_text("module top();\nendmodule\n", encoding="utf-8")
    pre_a = tmp_path / "a.f"
    pre_a.write_text("+define+A=1\n", encoding="utf-8")
    pre_b = tmp_path / "b.f"
    pre_b.write_text("+define+B=1\n", encoding="utf-8")
    db = tmp_path / "cache2.db"
    out = tmp_path / "out2.f"
    find_mock = MagicMock(side_effect=lambda m, *_: top if m == "top" else None)

    def run_pre(pre: Path) -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[rtl],
            top_modules=["top"],
            prelude_paths=[pre],
            output_path=out,
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = find_mock
        app.run()

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:
        ext.side_effect = lambda path, *_a, **_k: (["top"], [], [])
        run_pre(pre_a)
        warm = ext.call_count
        run_pre(pre_b)
    assert ext.call_count == warm + 1
