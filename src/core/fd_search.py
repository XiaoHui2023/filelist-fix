from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.hdl_extensions import HD_SOURCE_EXTENSIONS
from core.path_exclude import path_is_excluded
from core.path_logical import logical_abs


class FdModuleSearch:
    """用 fd 按「模块名与 basename 一致」在源树根下查找 HDL 文件。"""

    def __init__(self, fd_exe: str) -> None:
        self._fd = fd_exe

    def _regex(self, module_name: str) -> str:
        exts = "|".join(re.escape(e) for e in HD_SOURCE_EXTENSIONS)
        return rf"^{re.escape(module_name)}\.({exts})$"

    def search(
        self,
        module_name: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> Path | None:
        pattern = self._regex(module_name)
        best: Path | None = None
        excl = excludes or []
        for root in roots:
            try:
                cp = subprocess.run(
                    [self._fd, "--type", "f", pattern, str(root)],
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
                cand = logical_abs(Path(line))
                if path_is_excluded(cand, excl):
                    continue
                if best is None or len(cand.parts) < len(best.parts):
                    best = cand
        return best
