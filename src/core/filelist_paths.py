from __future__ import annotations

import os
from pathlib import Path


def format_listed_path(source_file: Path, output_file: Path, *, absolute: bool) -> str:
    """将源路径格式化为写入 filelist 正文的一行。

    Args:
        source_file: 闭包中的源文件路径（通常为已 resolve 的路径）。
        output_file: ``-o`` 指定的 filelist 路径。
        absolute: 为真写绝对路径；否则写相对于 ``output_file`` 父目录的路径（正斜杠）。

    Returns:
        写入 filelist 的一行路径字符串。
    """
    resolved = source_file.resolve()
    if absolute:
        return str(resolved)
    anchor = output_file.resolve().parent
    try:
        rel = os.path.relpath(resolved, anchor)
    except (OSError, ValueError):
        return str(resolved)
    return Path(rel).as_posix()
