from __future__ import annotations

from pathlib import Path


def path_is_excluded(candidate: Path, excludes: list[Path]) -> bool:
    """若 candidate 落在任一排除项之下则返回 True。

    比较前对候选与排除锚点均做 ``resolve(strict=False)``，使「经软链进入的源树」与「经软链给出的
    --exclude」与工具返回的真实路径一致，避免一侧为逻辑路径、一侧为物理路径导致漏判。

    Args:
        candidate: 待判断的路径（可为逻辑路径或已 resolve）。
        excludes: 已存在且可 resolve 的文件或目录；目录表示整棵子树，文件表示仅该文件。

    Returns:
        是否应排除。
    """
    if not excludes:
        return False
    c = candidate.resolve(strict=False)
    for ex in excludes:
        try:
            ex_res = ex.resolve(strict=False)
        except OSError:
            continue
        if ex_res.is_dir():
            if c == ex_res or c.is_relative_to(ex_res):
                return True
        elif c == ex_res:
            return True
    return False
