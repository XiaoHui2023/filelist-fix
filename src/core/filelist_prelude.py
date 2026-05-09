from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_INCDIR = re.compile(r"^\+incdir\+(\"([^\"]+)\"|(\S+))")
_DEFINE = re.compile(r"^\+define\+([A-Za-z_]\w*)(?:=(.*))?$")
_COMMENT = re.compile(r"^\s*//")


@dataclass
class PreludeOutcome:
    """filelist 前导片段解析结果：原样写入输出的行、以及影响解析的目录与宏。"""

    head_lines: list[str] = field(default_factory=list)
    incdirs: list[Path] = field(default_factory=list)
    defines: dict[str, str] = field(default_factory=dict)


def load_prelude_files(paths: list[Path]) -> PreludeOutcome:
    """按顺序读入多个 filelist/宏开关文件，汇总输出头与解析用指令。"""
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
                    out.incdirs.append(Path(inc).expanduser().resolve())
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
