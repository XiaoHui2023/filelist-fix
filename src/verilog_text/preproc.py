from __future__ import annotations

import re
from dataclasses import dataclass


def mask_preprocessor_comments(text: str) -> str:
    """Blank comments while retaining quoted include paths and line boundaries."""
    tokens = re.compile(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*', re.DOTALL)
    return tokens.sub(lambda m: m.group() if m.group().startswith('"') else
                      re.sub(r"[^\r\n]", " ", m.group()), text)


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
        self._macro_reads: set[str] = set()
        self._conditions: dict[str, bool] = {}
        self._local_changes: set[str] = set()
        self._local_all = False
        self._defined_here: set[str] = set()
        self._macro_events: list[str] = []
        self._macro_value_events: list[str] = []

    def _note_macro_read(self, name: str, *, condition: bool = False) -> None:
        if not name or self._local_all or name in self._local_changes:
            return
        self._macro_reads.add(name)
        if condition:
            self._conditions[name] = name in self.defines

    def macro_symbols(self) -> dict[str, list[str]]:
        return {
            'macro_uses': sorted(self._macro_reads),
            'macro_exports': sorted(self._defined_here & self.defines.keys()),
            'macro_events': list(self._macro_events),
            'macro_value_events': list(self._macro_value_events),
            'macro_condition_defined': sorted(n for n, defined in self._conditions.items() if defined),
            'macro_condition_undefined': sorted(n for n, defined in self._conditions.items() if not defined),
        }

    def _active_full(self) -> bool:
        base = True
        for fr in self._frames:
            base = base and fr.branch
        return base

    def handle_directive_line(self, line: str) -> bool:
        """若是预处理指令则处理并返回 True；否则返回 False 由上层按源码处理。"""
        m = re.match(
            r"^\s*`(ifdef|ifndef|elsif|else|endif|define|undef|undefineall)\b\s*(.*)$",
            line,
            re.IGNORECASE,
        )
        if not m:
            if '`' in line and self._active_full():
                source = re.sub(r'"(?:\\.|[^"\\])*"', '', line)
                for name in re.findall(r'`([A-Za-z_]\w*)', source):
                    self._note_macro_read(name)
            return False
        cmd, rest = m.group(1).lower(), m.group(2).strip()
        if cmd in {"ifdef", "ifndef", "elsif"}:
            name_m = re.match(r"^([A-Za-z_]\w*)\s*$", rest)
            name = name_m.group(1) if name_m else ""
        else:
            name = ""
        if cmd == "ifdef":
            parent = self._active_full()
            if parent:
                self._note_macro_read(name, condition=True)
            take = parent and (name in self.defines)
            self._frames.append(IfdefFrame(parent, take, take))
            return True
        if cmd == "ifndef":
            parent = self._active_full()
            if parent:
                self._note_macro_read(name, condition=True)
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
                self._note_macro_read(name, condition=True)
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
            dm = re.match(r"^([A-Za-z_]\w*)(?:\([^)]*\))?(?:\s+(.*))?$", rest)
            if dm:
                key, val = dm.group(1), dm.group(2) or ""
                self.defines[key] = val.strip()
                self._local_changes.add(key)
                self._defined_here.add(key)
                self._macro_events.append('define ' + key)
                self._macro_value_events.append('define ' + key + '=' + val.strip())
            return True
        if cmd == "undef":
            if not self._active_full():
                return True
            um = re.match(r"^([A-Za-z_]\w*)\s*$", rest)
            if um:
                key = um.group(1)
                self._local_changes.add(key)
                self._defined_here.discard(key)
                self._macro_events.append('undef ' + key)
                self._macro_value_events.append('undef ' + key)
            if um and um.group(1) in self.defines:
                del self.defines[um.group(1)]
            return True
        if cmd == "undefineall":
            if self._active_full():
                self.defines.clear()
                self._local_all = True
                self._defined_here.clear()
                self._macro_events.append('clear')
                self._macro_value_events.append('clear')
            return True
        return True

    def line_is_active_source(self) -> bool:
        """当前行若来自「应参与依赖抽取的源码分支」，返回 True。"""
        return self._active_full()
