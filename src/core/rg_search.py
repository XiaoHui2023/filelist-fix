from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core.hdl_extensions import rg_include_globs
from core.path_exclude import path_is_excluded
from core.path_logical import logical_abs


class RgModuleSearch:
    """用 rg 在源码中按 ``module`` / ``primitive`` / ``package`` 声明定位定义文件。"""

    def __init__(self, rg_exe: str) -> None:
        self._rg = rg_exe

    def _pattern(self, module_name: str) -> str:
        esc = re.escape(module_name)
        return rf"(?:module|primitive|package)\s+{esc}\b"

    def search_all(
        self,
        module_name: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> list[Path]:
        excl = excludes or []
        seen: set[Path] = set()
        hits: list[Path] = []
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
                return []
            if cp.returncode not in (0, 1):
                continue
            for line in (cp.stdout or "").splitlines():
                line = line.strip()
                if not line:
                    continue
                cand = logical_abs(Path(line))
                if path_is_excluded(cand, excl):
                    continue
                key = cand.resolve()
                if key in seen:
                    continue
                seen.add(key)
                hits.append(cand)
        hits.sort(key=lambda p: (len(p.parts), str(p)))
        return hits

    def search(
        self,
        module_name: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> Path | None:
        hits = self.search_all(module_name, roots, excludes)
        if len(hits) == 1:
            return hits[0]
        return None
