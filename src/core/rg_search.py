from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.hdl_extensions import rg_include_globs
from core.path_exclude import path_is_excluded


class RgModuleSearch:
    """用 rg 在源码中按 module 声明定位模块定义文件。"""

    def __init__(self, rg_exe: str) -> None:
        self._rg = rg_exe

    def _pattern(self, module_name: str) -> str:
        # Verilog UDP 与用户模块例化同形；定义关键字为 ``primitive``，须与 ``module`` 一并检索。
        esc = re.escape(module_name)
        return rf"(?:module|primitive)\s+{esc}\b"

    def search(
        self,
        module_name: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> Path | None:
        best: Path | None = None
        excl = excludes or []
        pat = self._pattern(module_name)
        for root in roots:
            cmd = [self._rg, "-l", "-S", "-e", pat]
            for g in rg_include_globs():
                cmd.extend(["--glob", g])
            cmd.append(str(root))
            try:
                cp = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
            except FileNotFoundError:
                return None
            if cp.returncode not in (0, 1):
                continue
            for line in (cp.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                cand = Path(line).resolve()
                if path_is_excluded(cand, excl):
                    continue
                if best is None or len(cand.parts) < len(best.parts):
                    best = cand
        return best
