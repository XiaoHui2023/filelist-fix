from __future__ import annotations

import shutil
import sys
from pathlib import Path


class ToolBinaryLocator:
    """在本地 tools/bin 与 PATH 中定位 rg、fd。"""

    def __init__(self, repo_root: Path | None = None) -> None:
        self._root = repo_root or self._infer_repo_root()

    @staticmethod
    def _infer_repo_root() -> Path:
        here = Path(__file__).resolve()
        for p in [here.parent] + list(here.parents):
            if (p / "tools").is_dir() and (p / "src").is_dir():
                return p
        return Path.cwd()

    def tools_bin(self) -> Path:
        return self._root / "tools" / "bin"

    def resolve_rg(self, override: Path | None) -> str:
        return self._resolve_one("rg", override, windows_name="rg.exe")

    def resolve_fd(self, override: Path | None) -> str:
        return self._resolve_one("fd", override, windows_name="fd.exe")

    def _resolve_one(self, unix_name: str, override: Path | None, *, windows_name: str) -> str:
        if override is not None:
            return str(override.expanduser().resolve())
        names = (windows_name, unix_name) if sys.platform.startswith("win") else (unix_name,)
        bin_dir = self.tools_bin()
        for n in names:
            p = bin_dir / n
            if p.is_file():
                return str(p.resolve())
        for n in names:
            w = shutil.which(n)
            if w:
                return w
        return unix_name


def normalize_search_roots(paths: list[Path]) -> list[Path]:
    """把用户输入规范成存在的目录或文件的绝对路径列表。"""
    out: list[Path] = []
    for p in paths:
        r = p.expanduser().resolve()
        if not r.exists():
            raise FileNotFoundError(str(r))
        out.append(r)
    return out


def path_stat_sig(p: Path) -> tuple[int, int]:
    st = p.stat()
    return (int(st.st_mtime_ns), int(st.st_size))
