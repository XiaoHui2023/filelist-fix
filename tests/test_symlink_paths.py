from __future__ import annotations

import os
from pathlib import Path

import pytest

from core.filelist_paths import format_listed_path
from core.path_logical import logical_abs


def test_logical_abs_preserves_symlink_dir_prefix(tmp_path: Path) -> None:
    real = tmp_path / "real_rtl"
    real.mkdir()
    (real / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    link = tmp_path / "src"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("无法创建目录符号链接（权限或平台限制）")
    via = link / "leaf.v"
    assert via.is_file()
    log = logical_abs(via)
    assert "src" in log.parts
    assert os.path.normpath(str(log)) == str(log)


def test_format_listed_path_absolute_keeps_symlink(tmp_path: Path) -> None:
    real = tmp_path / "real_rtl"
    real.mkdir()
    (real / "leaf.v").write_text("module leaf;\nendmodule\n", encoding="utf-8")
    link = tmp_path / "src"
    try:
        link.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("无法创建目录符号链接（权限或平台限制）")
    out = tmp_path / "out.f"
    line = format_listed_path(link / "leaf.v", out, absolute=True)
    assert "src" in Path(line).parts
