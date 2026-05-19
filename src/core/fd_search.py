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

    def _regex_module_basename(self, module_name: str) -> str:
        exts = "|".join(re.escape(e) for e in HD_SOURCE_EXTENSIONS)
        return rf"^{re.escape(module_name)}\.({exts})$"

    def _regex_filename(self, filename: str) -> str:
        return rf"(?:^|[/\\]){re.escape(filename)}$"

    def _run_fd(self, pattern: str, root: Path) -> list[str]:
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
            return []
        if cp.returncode not in (0, 1):
            return []
        return [ln.strip() for ln in (cp.stdout or "").splitlines() if ln.strip()]

    def _collect(
        self,
        pattern: str,
        roots: list[Path],
        excludes: list[Path] | None,
    ) -> list[Path]:
        excl = excludes or []
        seen: set[Path] = set()
        hits: list[Path] = []
        for root in roots:
            for line in self._run_fd(pattern, root):
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

    def search_all(
        self,
        module_name: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> list[Path]:
        """按模块名等于 basename 收集全部未排除命中（0/1/多）。"""
        pattern = self._regex_module_basename(module_name)
        return self._collect(pattern, roots, excludes)

    def search_by_filename(
        self,
        filename: str,
        roots: list[Path],
        excludes: list[Path] | None = None,
    ) -> list[Path]:
        """按 include 目标文件名在源树中收集全部未排除命中。"""
        name = Path(filename).name
        if not name:
            return []
        pattern = self._regex_filename(name)
        return self._collect(pattern, roots, excludes)

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
