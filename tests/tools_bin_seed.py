"""测试用：检查工程内 tools/bin 是否已安装 rg/fd。"""

from __future__ import annotations

import sys
from pathlib import Path


def project_has_tools_bin(project_root: Path) -> bool:
    """工程根下 tools/bin 是否已具备 rg 与 fd。"""
    b = project_root / "tools" / "bin"
    if sys.platform.startswith("win"):
        return (b / "rg.exe").is_file() and (b / "fd.exe").is_file()
    return (b / "rg").is_file() and (b / "fd").is_file()
