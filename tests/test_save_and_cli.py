from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_save_skips_reparse_on_second_run(tmp_path: Path) -> None:
    src = tmp_path / "rtl"
    src.mkdir()
    (src / "leaf.v").write_text("module leaf();\nendmodule\n", encoding="utf-8")
    (src / "top.v").write_text("module top();\n  leaf u1();\nendmodule\n", encoding="utf-8")
    db = tmp_path / "parse_cache.db"

    hits = {"top": src / "top.v", "leaf": src / "leaf.v"}
    find_mock = MagicMock(side_effect=lambda m, *_: hits.get(m))

    def run_once() -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[src],
            top_modules=["top"],
            prelude_paths=[],
            output_path=tmp_path / "save_run.f",
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = find_mock
        app.run()

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:

        def _fake(path: Path, *_a: object, **_k: object) -> tuple[list[str], list[str], list[str]]:
            if path.name == "top.v":
                return (["top"], ["leaf"], [])
            return (["leaf"], [], [])

        ext.side_effect = _fake
        run_once()
        first = ext.call_count
        find_after_first = find_mock.call_count
        run_once()
        second = ext.call_count
        find_after_second = find_mock.call_count
    assert first == 2
    assert second == 2
    assert find_after_first == 2
    assert find_after_second == 2


def test_save_leaf_change_refinds_leaf_only(tmp_path: Path) -> None:
    src = tmp_path / "rtl"
    src.mkdir()
    leaf = src / "leaf.v"
    top = src / "top.v"
    leaf.write_text("module leaf();\nendmodule\n", encoding="utf-8")
    top.write_text("module top();\n  leaf u1();\nendmodule\n", encoding="utf-8")
    db = tmp_path / "parse_cache.db"
    hits = {"top": top, "leaf": leaf}
    find_mock = MagicMock(side_effect=lambda m, *_: hits.get(m))

    def run_app() -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[src],
            top_modules=["top"],
            prelude_paths=[],
            output_path=tmp_path / "save_run.f",
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = find_mock
        app.run()

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:

        def _fake(path: Path, *_a: object, **_k: object) -> tuple[list[str], list[str], list[str]]:
            if path.name == "top.v":
                return (["top"], ["leaf"], [])
            return (["leaf"], [], [])

        ext.side_effect = _fake
        run_app()
        run_app()
        find_warm = find_mock.call_count
        ext_warm = ext.call_count
        leaf.write_text("module leaf();\n// touch\nendmodule\n", encoding="utf-8")
        run_app()
    assert ext.call_count == ext_warm + 1
    assert find_mock.call_count == find_warm


def test_save_top_change_refinds_refs(tmp_path: Path) -> None:
    src = tmp_path / "rtl2"
    src.mkdir()
    leaf = src / "leaf.v"
    top = src / "top.v"
    leaf.write_text("module leaf();\nendmodule\n", encoding="utf-8")
    top.write_text("module top();\n  leaf u1();\nendmodule\n", encoding="utf-8")
    db = tmp_path / "parse_cache2.db"
    hits = {"top": top, "leaf": leaf}
    find_mock = MagicMock(side_effect=lambda m, *_: hits.get(m))

    def run_app() -> None:
        ctx = AppContext(logger=None, console=None)
        app = FilelistApplication(
            search_roots=[src],
            top_modules=["top"],
            prelude_paths=[],
            output_path=tmp_path / "save_run2.f",
            save_path=db,
            ctx=ctx,
        )
        app._tools.find_file = find_mock
        app.run()

    with patch("runtime.filelist_app.extract_dependencies_from_file") as ext:

        def _fake(path: Path, *_a: object, **_k: object) -> tuple[list[str], list[str], list[str]]:
            if path.name == "top.v":
                return (["top"], ["leaf"], [])
            return (["leaf"], [], [])

        ext.side_effect = _fake
        run_app()
        run_app()
        find_warm = find_mock.call_count
        ext_warm = ext.call_count
        top.write_text("module top();\n  leaf u1();\n// edit\nendmodule\n", encoding="utf-8")
        run_app()
    assert ext.call_count == ext_warm + 1
    assert find_mock.call_count == find_warm + 1


def test_cli_writes_summary_to_stderr(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    from tools_bin_seed import project_has_tools_bin

    if not project_has_tools_bin(root):
        pytest.skip("工程 tools/bin 下缺少 rg/fd，请先运行 tools 下载脚本")
    rtl = root / "example" / "complex_rtl"
    prelude = root / "example" / "run_prelude.f"
    out = tmp_path / "out.f"
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "src"),
            "--source",
            str(rtl),
            "-t",
            "top_chip",
            "-p",
            str(prelude),
            "-o",
            str(out),
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    body = out.read_text(encoding="utf-8")
    assert "top_chip.v" in body
    lines = [Path(ln.strip()).as_posix() for ln in body.splitlines() if ln.strip()]
    assert any(ln.endswith("complex_rtl/top_chip.v") for ln in lines)
    assert proc.stdout.strip() == ""
    assert str(out.resolve()) in proc.stderr


def test_cli_absolute_path_style(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    from tools_bin_seed import project_has_tools_bin

    if not project_has_tools_bin(root):
        pytest.skip("工程 tools/bin 下缺少 rg/fd，请先运行 tools 下载脚本")
    rtl = root / "example" / "complex_rtl"
    prelude = root / "example" / "run_prelude.f"
    out = tmp_path / "abs.f"
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "src"),
            "--source",
            str(rtl),
            "-t",
            "top_chip",
            "-p",
            str(prelude),
            "-o",
            str(out),
            "--path-style",
            "absolute",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    lines = [ln.strip() for ln in out.read_text(encoding="utf-8").splitlines() if ln.strip()]
    path_lines = [
        ln
        for ln in lines
        if not ln.startswith("+") and not ln.startswith("-") and not ln.startswith("`")
    ]
    assert path_lines
    assert all(Path(ln).is_absolute() for ln in path_lines)
