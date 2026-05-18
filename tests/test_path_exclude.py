from __future__ import annotations

from pathlib import Path

import pytest

from core.path_exclude import path_is_excluded
from core.path_logical import logical_abs


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


def test_exclude_symlink_anchor_matches_physically_resolved_candidate(tmp_path: Path) -> None:
    """排除项经软链给出、候选为物理路径时仍应命中（与 fd/rg 返回路径形态一致）。"""
    real = tmp_path / "real_rtl"
    bad = real / "vendor" / "bad"
    bad.mkdir(parents=True)
    f = bad / "x.sv"
    f.write_text("module x;\nendmodule\n", encoding="utf-8")
    link_rtl = tmp_path / "src"
    try:
        link_rtl.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("无法创建目录符号链接（权限或平台限制）")
    excl = logical_abs(link_rtl / "vendor" / "bad")
    assert excl.exists()
    assert path_is_excluded(f.resolve(), [excl])
    assert path_is_excluded(logical_abs(f), [excl])
