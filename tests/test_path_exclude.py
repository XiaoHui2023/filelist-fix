from __future__ import annotations

from pathlib import Path

from core.path_exclude import path_is_excluded


def test_exclude_dir_covers_descendants(tmp_path: Path) -> None:
    root = tmp_path / "rtl"
    root.mkdir()
    sub = root / "vendor" / "x"
    sub.mkdir(parents=True)
    f = sub / "m.sv"
    f.write_text("module m;\nendmodule\n", encoding="utf-8")
    excl = (tmp_path / "rtl" / "vendor").resolve()
    assert path_is_excluded(f.resolve(), [excl])
    assert not path_is_excluded((root / "good.sv").resolve(), [excl])


def test_exclude_file_only_exact(tmp_path: Path) -> None:
    f = tmp_path / "only.v"
    f.write_text("", encoding="utf-8")
    other = tmp_path / "other.v"
    other.write_text("", encoding="utf-8")
    assert path_is_excluded(f.resolve(), [f.resolve()])
    assert not path_is_excluded(other.resolve(), [f.resolve()])


def test_empty_excludes_never_matches(tmp_path: Path) -> None:
    assert not path_is_excluded(tmp_path.resolve(), [])
