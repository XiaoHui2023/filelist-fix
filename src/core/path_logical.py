from __future__ import annotations

import os
from pathlib import Path


def logical_abs(path: Path) -> Path:
    """展开 ``~`` 后取绝对路径并做 normpath，不解析符号链接。

    用于 filelist、prelude、include 解析等输出与用户可见路径，保留经符号链接访问时的路径前缀。

    Args:
        path: 任意 ``pathlib.Path``。

    Returns:
        不跟随符号链接的绝对 ``Path``（与 ``os.path.abspath`` 语义一致）。
    """
    p = path.expanduser()
    return Path(os.path.normpath(os.path.abspath(os.fspath(p))))
