from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class IfdefFrame:
    parent_active: bool
    branch: bool
    had_true: bool


class PreprocDirectiveParser:
    """按行处理 Verilog/SystemVerilog 预处理指令与简单 `define / `undef。"""

    def __init__(self, defines: dict[str, str] | None = None) -> None:
        self.defines: dict[str, str] = dict(defines or {})
        self._frames: list[IfdefFrame] = []

    def _active_full(self) -> bool:
        base = True
        for fr in self._frames:
            base = base and fr.branch
        return base

    def handle_directive_line(self, line: str) -> bool:
        """若是预处理指令则处理并返回 True；否则返回 False 由上层按源码处理。"""
        m = re.match(
            r"^\s*`(ifdef|ifndef|elsif|else|endif|define|undef)\b\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if not m:
            return False
        cmd, rest = m.group(1).lower(), m.group(2).strip()
        if cmd in {"ifdef", "ifndef", "elsif"}:
            name_m = re.match(r"^([A-Za-z_]\w*)\s*$", rest)
            name = name_m.group(1) if name_m else ""
        else:
            name = ""
        if cmd == "ifdef":
            parent = self._active_full()
            take = parent and (name in self.defines)
            self._frames.append(IfdefFrame(parent, take, take))
            return True
        if cmd == "ifndef":
            parent = self._active_full()
            take = parent and (name not in self.defines)
            self._frames.append(IfdefFrame(parent, take, take))
            return True
        if cmd == "elsif":
            if not self._frames:
                return True
            fr = self._frames[-1]
            if not fr.parent_active:
                fr.branch = False
                return True
            if fr.had_true:
                fr.branch = False
            else:
                take = name in self.defines
                fr.branch = take
                fr.had_true = fr.had_true or take
            return True
        if cmd == "else":
            if not self._frames:
                return True
            fr = self._frames[-1]
            if not fr.parent_active:
                fr.branch = False
            elif fr.had_true:
                fr.branch = False
            else:
                fr.branch = True
                fr.had_true = True
            return True
        if cmd == "endif":
            if self._frames:
                self._frames.pop()
            return True
        if cmd == "define":
            if not self._active_full():
                return True
            dm = re.match(r"^([A-Za-z_]\w*)(?:\s+(.*))?$", rest)
            if dm:
                key, val = dm.group(1), dm.group(2) or ""
                self.defines[key] = val.strip()
            return True
        if cmd == "undef":
            if not self._active_full():
                return True
            um = re.match(r"^([A-Za-z_]\w*)\s*$", rest)
            if um and um.group(1) in self.defines:
                del self.defines[um.group(1)]
            return True
        return True

    def line_is_active_source(self) -> bool:
        """当前行若来自「应参与依赖抽取的源码分支」，返回 True。"""
        return self._active_full()
