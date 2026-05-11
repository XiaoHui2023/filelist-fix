from __future__ import annotations

from pathlib import Path


def path_is_excluded(candidate: Path, excludes: list[Path]) -> bool:
    """若 candidate（建议已 resolve）落在任一排除项之下则返回 True。

    Args:
        candidate: 待判断的路径。
        excludes: 已 resolve 且存在的路径；目录表示整棵子树，文件表示仅该文件。

    Returns:
        是否应排除。
    """
    if not excludes:
        return False
    c = candidate.resolve()
    for ex in excludes:
        if ex.is_dir():
            if c == ex or c.is_relative_to(ex):
                return True
        elif c == ex:
            return True
    return False
