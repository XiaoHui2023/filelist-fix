from __future__ import annotations

import os
from pathlib import Path

from core.filelist_paths import format_listed_path
from core.path_logical import logical_abs


def test_format_listed_path_relative(tmp_path: Path) -> None:
    sub = tmp_path / "rtl"
    sub.mkdir()
    f = sub / "a.v"
    f.write_text("module a;\nendmodule\n", encoding="utf-8")
    out = tmp_path / "out" / "list.f"
    out.parent.mkdir(parents=True, exist_ok=True)
    rel = format_listed_path(f, out, absolute=False)
    assert rel == Path(os.path.relpath(logical_abs(f), logical_abs(out).parent)).as_posix()
    assert not Path(rel).is_absolute()


def test_format_listed_path_absolute(tmp_path: Path) -> None:
    f = tmp_path / "x.v"
    f.write_text("module x;\nendmodule\n", encoding="utf-8")
    out = tmp_path / "list.f"
    s = format_listed_path(f, out, absolute=True)
    assert s == str(logical_abs(f))
