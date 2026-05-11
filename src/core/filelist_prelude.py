from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_INCDIR = re.compile(r"^\+incdir\+(\"([^\"]+)\"|(\S+))")
_DEFINE = re.compile(r"^\+define\+([A-Za-z_]\w*)(?:=(.*))?$")
_COMMENT = re.compile(r"^\s*//")


def _resolve_incdir(prelude_file: Path, inc: str) -> Path:
    """将 +incdir+ 路径解析为绝对路径；相对路径相对于该 prelude 文件所在目录。"""
    raw = Path(inc).expanduser()
    if raw.is_absolute():
        return raw.resolve()
    return (prelude_file.parent / raw).resolve()


@dataclass
class PreludeOutcome:
    """filelist 前导片段解析结果：原样写入输出的行、以及影响解析的目录与宏。"""

    head_lines: list[str] = field(default_factory=list)
    incdirs: list[Path] = field(default_factory=list)
    defines: dict[str, str] = field(default_factory=dict)


def load_prelude_files(paths: list[Path]) -> PreludeOutcome:
    """按顺序读入多个 filelist/宏开关文件，汇总输出头与解析用指令。

    ``+incdir+`` 若为相对路径，则相对于**当前正在读取的该 prelude 文件**所在目录解析。
    """
    out = PreludeOutcome()
    for p in paths:
        raw = p.read_text(encoding="utf-8", errors="replace")
        for line in raw.splitlines():
            s = line.strip()
            if not s or _COMMENT.match(s):
                continue
            im = _INCDIR.match(s)
            if im:
                inc = im.group(2) or im.group(3) or ""
                if inc:
                    out.incdirs.append(_resolve_incdir(p, inc))
                continue
            dm = _DEFINE.match(s)
            if dm:
                k, v = dm.group(1), dm.group(2) or ""
                out.defines[k] = v.strip()
                continue
            if s.startswith("+"):
                out.head_lines.append(line)
                continue
            out.head_lines.append(line)
    return out
