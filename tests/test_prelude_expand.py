from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from core.archive_sqlite import FileParseArchive
from core.filelist_prelude import load_prelude_files_with_signature, prelude_signature_from_files
from core.path_logical import logical_abs
from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_nested_f_expands_in_order(tmp_path: Path) -> None:
    inner = tmp_path / "inner.f"
    inner.write_text("+define+INNER=1\n", encoding="utf-8")
    root = tmp_path / "root.f"
    root.write_text('+define+ROOT=1\n-f inner.f\n+define+AFTER=1\n', encoding="utf-8")
    out_anchor = tmp_path / "out.f"
    pre, _sig = load_prelude_files_with_signature(
        [root], output_path=out_anchor, path_absolute=False
    )
    assert pre.defines["ROOT"] == "1"
    assert pre.defines["INNER"] == "1"
    assert pre.defines["AFTER"] == "1"
    joined = "\n".join(pre.head_lines)
    assert "+define+ROOT=1" in joined
    assert "+define+INNER=1" in joined
    assert "+define+AFTER=1" in joined
    assert "-f" not in joined


def test_prelude_hdl_file_single_line(tmp_path: Path) -> None:
    v = tmp_path / "chip.sv"
    v.write_text("module chip;\nendmodule\n", encoding="utf-8")
    out = tmp_path / "out.f"
    pre, _ = load_prelude_files_with_signature([v], output_path=out, path_absolute=False)
    assert len(pre.head_lines) == 1
    assert pre.head_lines[0].replace("\\", "/") == "chip.sv"


def test_archive_invalidates_when_nested_prelude_mtime_changes(tmp_path: Path) -> None:
    rtl = tmp_path / "rtl"
    rtl.mkdir()
    (rtl / "leaf.v").write_text("module leaf();\nendmodule\n", encoding="utf-8")
    (rtl / "top.v").write_text("module top();\n  leaf u1();\nendmodule\n", encoding="utf-8")

    nested = tmp_path / "nested.f"
    nested.write_text("+define+FROM_NEST=1\n", encoding="utf-8")
    root = tmp_path / "root.f"
    root.write_text(f"-f {nested.as_posix()}\n", encoding="utf-8")

    db = tmp_path / "cache.db"
    out = tmp_path / "run.f"
    hits = {"top": rtl / "top.v", "leaf": rtl / "leaf.v"}

    def run_app() -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[rtl],
            top_modules=["top"],
            prelude_paths=[root],
            output_path=out,
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = lambda m, *_: hits.get(m)
        app.run()

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:

        def _fake(path: Path, *_a: object, **_k: object) -> tuple[list[str], list[str], list[str]]:
            if path.name == "top.v":
                return (["top"], ["leaf"], [])
            return (["leaf"], [], [])

        ext.side_effect = _fake
        run_app()
        mid = ext.call_count
        nested.write_text("+define+FROM_NEST=2\n", encoding="utf-8")
        run_app()
        assert ext.call_count > mid


def test_signature_stable_for_same_files(tmp_path: Path) -> None:
    a = tmp_path / "a.f"
    a.write_text("+define+X=1\n", encoding="utf-8")
    out = tmp_path / "o.f"
    _, s1 = load_prelude_files_with_signature([a], output_path=out, path_absolute=False)
    _, s2 = load_prelude_files_with_signature([a], output_path=out, path_absolute=False)
    assert s1 == s2
    assert s1 == prelude_signature_from_files([logical_abs(a)])
