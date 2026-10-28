# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 规格：onefile 单可执行文件，附带 bundle 内 tools/bin（rg、fd）。

构建入口：仓库根执行 bash tools/pack.sh（内部会下载 rg/fd、用 .venv 跑 PyInstaller；
Linux 上再跑 staticx）。仅打 spec 时请先自行执行 tools/download_rg_fd.sh 或 .bat。
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyInstaller.building.api import EXE, PYZ
from PyInstaller.building.build_main import Analysis
from PyInstaller.utils.hooks import collect_submodules

block_cipher = None


def _repo_root_from_spec() -> Path:
    """SPECPATH 常为相对路径，resolve 依赖 cwd；从 spec 所在目录与 cwd 双向向上找含 pyproject.toml 的仓库根。"""
    spec = Path(SPECPATH).resolve()
    seeds = [spec.parent]
    try:
        seeds.append(Path.cwd().resolve())
    except OSError:
        pass
    for seed in seeds:
        for base in [seed, *seed.parents]:
            if (base / "pyproject.toml").is_file() and (base / "src" / "__main__.py").is_file():
                return base
    return spec.parent


repo_root = _repo_root_from_spec()
src_main = repo_root / "src" / "__main__.py"

sys.path.insert(0, str(repo_root / "src"))
sys.path.insert(0, str(repo_root / "tools"))
from release_support import binary_name

tools_bin = repo_root / "tools" / "bin"
datas: list[tuple[str, str]] = []
if tools_bin.is_dir():
    datas.append((str(tools_bin), "tools/bin"))
notices = repo_root / "build" / "release-notices"
if not notices.is_dir():
    raise RuntimeError("Run tools/pack.bat or tools/pack.sh to collect required notices first")
datas.append((str(notices), "licenses"))

hiddenimports = sorted(
    set(collect_submodules("impl") + collect_submodules("api")),
)

a = Analysis(
    [str(src_main)],
    pathex=[str(repo_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=binary_name().removesuffix(".exe"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
