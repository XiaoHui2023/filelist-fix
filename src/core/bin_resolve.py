from __future__ import annotations

import sys
from pathlib import Path


class ToolBinaryLocator:
    """仅在仓库 `tools/bin` 下定位 rg、fd（不读 PATH；仓库根由本包相对路径推断）。"""

    def __init__(self) -> None:
        self._root = self._infer_repo_root()

    @staticmethod
    def _infer_repo_root() -> Path:
        here = Path(__file__).resolve()
        for p in [here.parent] + list(here.parents):
            if (p / "tools").is_dir() and (p / "src").is_dir():
                return p
        return Path.cwd()

    def tools_bin(self) -> Path:
        return self._root / "tools" / "bin"

    def resolve_rg(self) -> str:
        return self._resolve_one("rg", windows_name="rg.exe")

    def resolve_fd(self) -> str:
        return self._resolve_one("fd", windows_name="fd.exe")

    def _resolve_one(self, unix_name: str, *, windows_name: str) -> str:
        names = (windows_name, unix_name) if sys.platform.startswith("win") else (unix_name,)
        bin_dir = self.tools_bin()
        for n in names:
            p = bin_dir / n
            if p.is_file():
                return str(p.resolve())
        raise FileNotFoundError(
            f"未在 {bin_dir} 找到 {unix_name}（尝试过: {', '.join(names)}）。"
            f"请在本仓库运行 tools 下的下载脚本，将 rg、fd 安装到 tools/bin。",
        )


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
