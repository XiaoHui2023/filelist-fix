from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path

_README = """依赖解析调试输出（本目录由 --debug-dump 生成）

工具**不在**本目录写入任何日历日期、时钟时间或进程号类旁路文件；日志请用 **`-l`**，与这里无关。

每次带 **`--debug-dump`** 的进程启动时，会先**清空并重建** **`by_file/`** 子目录，再写入本轮解析产生的子目录与片段；因此目录里**只保留本次运行**写出的内容，不会残留上一轮其它源文件的子目录。根目录 **`README.txt`** 每次覆盖为当前说明文本。

## 子目录名里末尾的十六进制串是什么

`by_file/` 下每个子目录通常名为**去掉扩展名后的短文件名**（非字母数字等字符会换成下划线，过长会截断）。**仅当**本轮解析中**多个不同源文件**在用过上述规则后会**同名**时，才在目录名末尾追加 `_` + **16 位小写十六进制**；该串是 **SHA256（UTF-8 编码的该源文件绝对路径）取前 16 个十六进制字符**，由路径唯一确定，**不是随机数、也不是日期**。用途：不同路径下若基名相同，仍能得到不同子目录。

## 重复生成与同一路径

- **`by_file/`** 见上文：每进程启动**整目录清空后重建**，仅本轮会写盘。
- **`00_source_path.txt`** 随该源文件在本轮被解析时写入或刷新。
- 若启用 **`--save`** 且某源未变、走缓存跳过解析，则**本轮不会**为该源再写调试片段（该源也不会出现新的 `by_file` 子目录）。
- 需要保留多份历史时，请每次指定**不同的** `--debug-dump` 输出根目录。
- 两个进程**同时**指向同一 `--debug-dump` 目录时可能交错写文件，不建议共用。

## 单文件在 by_file 下的含义

每个被解析的源文件对应一个子目录（命名规则见上；无同名冲突时不带十六进制尾缀）。
目录内各文件大致对应流水线顺序（与实现一致）：

1. 00_source_path.txt — 该目录对应的源文件绝对路径。
2. 01_joined.txt — 读盘后做反斜杠续行折叠的结果（尚未跑 ifdef 等预处理行）。
3. 02_flatten_merged.txt — 在当前宏与 ifdef 活动分支下，本文件行与已展开 include 子树拼成的一段文本（递归时每个物理文件各有一份目录）。
4. 03a_strip_comments.txt — 去掉 // 与块注释、尽量保留串内形状后的文本。
5. 03b_drop_alwaysish.txt — 再删掉 **always / always_ff / always_comb / always_latch**、**initial**、**final** 等过程块，以及 **task…endtask**、**extern task** 原型、**specify…endspecify**、**generate…endgenerate**（启发式；与例化无关的整块先行去掉以缩短后续扫描文本；**generate 内例化不再参与依赖抽取**）。
6. 03c_strip_decl_noise.txt — 按行去掉 **assign**（含**多行右值**直至行内顶层 ``;``）、port 方向（input/output/inout）、ref、wire/reg/logic 等声明行；**localparam / parameter / localparameter** 支持**多行逗号续写**直至行内顶层 ``;``；以及 `` `timescale``、`` `celldefine`` / `` `endcelldefine`` 等编译指令整行（启发式，减轻误匹配）。
7. 03d0_pre_strip_module_ports.txt — 与 **03c** 阶段文本相同，专作与下一步对照（进入各 module 体内端口头剥离前的快照）。
8. 03d_strip_module_ports.txt — 在每个 module…endmodule 体内去掉实为 module 头的 ``#(…)`` 与端口表等残留；体首若为带 ``#(…)`` 的例化则保留，避免误剥。
9. 03e_scan_input.txt — 在 **03d** 之后将**已识别例化**的最外层端口括弧内部换成空白（减轻误匹配、便于按行粗查），再送入 `scan_verilog_body`（与 `SqueezeForDependencyScanAPI` 输出一致）。
10. 04_scan_result.txt — defined / referenced / include 列表摘要。
11. 05_instance_scan_trace.txt — 各 module 体内及全文件 bind 第二遍的逐行判定：MATCH（模块类型与规则简述）、SKIP（未匹配原因）、BIND。

说明：未指定 -l 时仍可写本目录；与文件日志无关。走解析缓存命中且未重新抽取依赖时，不会再次为同一文件写这些片段。
"""


class DependencyDebugDump:
    """把单文件依赖抽取各阶段的文本落到磁盘，便于对照「哪一步之后不像预期」。

    每次构造时清空 by_file/ 后重写 README.txt；不写日期时间类旁路文件。
    """

    def __init__(self, root: Path) -> None:
        self._root = root.resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        by_file = self._root / "by_file"
        if by_file.is_dir():
            shutil.rmtree(by_file)
        by_file.mkdir(parents=True, exist_ok=True)
        readme = self._root / "README.txt"
        readme.write_text(_README, encoding="utf-8", newline="\n")
        legacy = self._root / "last_run.txt"
        if legacy.exists():
            legacy.unlink()

        self._resolved_dir: dict[str, Path] = {}
        self._stem_collided: set[str] = set()

    @staticmethod
    def _hash16(resolved: Path) -> str:
        return hashlib.sha256(str(resolved).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _sanitize_stem(source_path: Path) -> str:
        stem = "".join(c if c.isalnum() or c in "._-" else "_" for c in source_path.stem)[:48]
        return stem if stem else "_"

    @staticmethod
    def _marker_same_source(marker_text: str, resolved: Path) -> bool:
        t = marker_text.strip()
        if t == str(resolved):
            return True
        if not t:
            return True
        prev = Path(t)
        try:
            prev_res = prev.resolve()
        except OSError:
            return True
        try:
            exists = prev_res.exists()
        except OSError:
            return True
        if not exists:
            return True
        try:
            return os.path.samefile(prev_res, resolved)
        except OSError:
            return False

    def _target_dir(self, source_path: Path) -> Path:
        resolved = source_path.resolve()
        key = str(resolved)
        hit = self._resolved_dir.get(key)
        if hit is not None:
            d = hit
            (d / "00_source_path.txt").write_text(
                str(resolved),
                encoding="utf-8",
                newline="\n",
            )
            return d

        stem = self._sanitize_stem(source_path)
        by_file = self._root / "by_file"

        if stem in self._stem_collided:
            d = by_file / f"{stem}_{self._hash16(resolved)}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "00_source_path.txt").write_text(
                str(resolved),
                encoding="utf-8",
                newline="\n",
            )
            self._resolved_dir[key] = d
            return d

        plain = by_file / stem
        if plain.is_dir():
            marker = plain / "00_source_path.txt"
            prev = marker.read_text(encoding="utf-8") if marker.is_file() else ""
            if self._marker_same_source(prev, resolved):
                d = plain
            else:
                self._stem_collided.add(stem)
                old_txt = prev.strip()
                old_res = Path(old_txt).resolve() if old_txt else resolved
                hashed_old = by_file / f"{stem}_{self._hash16(old_res)}"
                if hashed_old.exists():
                    raise FileExistsError(f"debug dump rename target exists: {hashed_old}")
                plain.rename(hashed_old)
                self._resolved_dir[str(old_res)] = hashed_old
                d = by_file / f"{stem}_{self._hash16(resolved)}"
                d.mkdir(parents=True, exist_ok=True)
        else:
            d = plain
            d.mkdir(parents=True, exist_ok=True)

        (d / "00_source_path.txt").write_text(
            str(resolved),
            encoding="utf-8",
            newline="\n",
        )
        self._resolved_dir[key] = d
        return d

    def write_text(self, source_path: Path, filename: str, text: str) -> None:
        """写入给定源文件调试目录下的一个片段文件。"""
        d = self._target_dir(source_path)
        (d / filename).write_text(text, encoding="utf-8", newline="\n")
