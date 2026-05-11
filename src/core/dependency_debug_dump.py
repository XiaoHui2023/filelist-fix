from __future__ import annotations

import hashlib
from pathlib import Path

_README = """依赖解析调试输出（本目录由 --debug-dump 生成）

## 单文件在 by_file 下的含义

每个被解析的源文件对应一个子目录，名为「短文件名 + 路径哈希」，避免不同路径同名冲突。
目录内各文件大致对应流水线顺序（与实现一致）：

1. 00_source_path.txt — 该目录对应的源文件绝对路径。
2. 01_joined.txt — 读盘后做反斜杠续行折叠的结果（尚未跑 ifdef 等预处理行）。
3. 02_flatten_merged.txt — 在当前宏与 ifdef 活动分支下，本文件行与已展开 include 子树拼成的一段文本（递归时每个物理文件各有一份目录）。
4. 03a_strip_comments.txt — 去掉 // 与块注释、尽量保留串内形状后的文本。
5. 03b_drop_alwaysish.txt — 再删掉 always / initial / final 等过程块（启发式，减轻后续正则量）。
6. 03c_squeeze_full.txt — 与正式管线中 squeeze 一步输出一致（应与 03b 等价，用于核对）。
7. 04_scan_result.txt — 对 squeeze 后文本做 module、例化、bind、include 扫描得到的 defined / referenced / include 列表摘要。

说明：未指定 -l 时仍可写本目录；与文件日志无关。走解析缓存命中且未重新抽取依赖时，不会再次为同一文件写这些片段。
"""


class DependencyDebugDump:
    """把单文件依赖抽取各阶段的文本落到磁盘，便于对照「哪一步之后不像预期」。"""

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        readme = self._root / "README.txt"
        if not readme.exists():
            readme.write_text(_README, encoding="utf-8", newline="\n")

    def _target_dir(self, source_path: Path) -> Path:
        h = hashlib.sha256(str(source_path.resolve()).encode("utf-8")).hexdigest()[:16]
        stem = "".join(c if c.isalnum() or c in "._-" else "_" for c in source_path.stem)[:48]
        d = self._root / "by_file" / f"{stem}_{h}"
        d.mkdir(parents=True, exist_ok=True)
        marker = d / "00_source_path.txt"
        if not marker.exists():
            marker.write_text(str(source_path.resolve()), encoding="utf-8", newline="\n")
        return d

    def write_text(self, source_path: Path, filename: str, text: str) -> None:
        """写入给定源文件调试目录下的一个片段文件。"""
        d = self._target_dir(source_path)
        (d / filename).write_text(text, encoding="utf-8", newline="\n")
