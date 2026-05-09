from __future__ import annotations

import re
from dataclasses import dataclass

_MODULE_HEAD = re.compile(
    r"(?m)^\s*module\s+(?:automatic\s+)?([A-Za-z_]\w*)\b",
)
_ENDMODULE = re.compile(r"(?m)^\s*endmodule\b")
_INCLUDE = re.compile(r"^\s*`include\s+(?:\"([^\"]+)\"|<([^>]+)>)\s*$")
_kw = {
    "if",
    "while",
    "for",
    "repeat",
    "forever",
    "case",
    "casex",
    "casez",
    "do",
    "foreach",
    "assert",
    "assume",
    "cover",
    "wait",
    "return",
}
_INSTANCE = re.compile(
    r"(?m)^\s*([A-Za-z_]\w*)\s+([A-Za-z_]\w*)\s*(?:#\s*\([^;]*?\))?\s*\(",
)


@dataclass
class VerilogSliceScan:
    defined_modules: list[str]
    referenced_modules: list[str]
    include_paths: list[str]


def scan_verilog_body(text: str) -> VerilogSliceScan:
    """从已通过条件编译筛选且压缩过的文本中抽取模块名、实例与 include。"""
    defs: list[str] = []
    refs: list[str] = []
    incs: list[str] = []
    pos = 0
    while True:
        mh = _MODULE_HEAD.search(text, pos)
        if not mh:
            break
        end = _ENDMODULE.search(text, mh.end())
        if not end:
            break
        name = mh.group(1)
        defs.append(name)
        body = text[mh.end() : end.start()]
        for im in _INCLUDE.finditer(body):
            p = im.group(1) or im.group(2) or ""
            if p:
                incs.append(p.strip())
        for vm in _INSTANCE.finditer(body):
            t, inst = vm.group(1), vm.group(2)
            if t in _kw or inst in _kw:
                continue
            if t == name:
                continue
            refs.append(t)
        pos = end.end()
    if not defs:
        for im in _INCLUDE.finditer(text):
            p = im.group(1) or im.group(2) or ""
            if p:
                incs.append(p.strip())
        for vm in _INSTANCE.finditer(text):
            t = vm.group(1)
            if t not in _kw:
                refs.append(t)
    return VerilogSliceScan(
        defined_modules=sorted(set(defs)),
        referenced_modules=sorted(set(refs)),
        include_paths=sorted(set(incs)),
    )
