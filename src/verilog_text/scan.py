from __future__ import annotations

import re
from dataclasses import dataclass

_MODULE_HEAD = re.compile(
    r"(?m)^\s*module\s+(?:automatic\s+)?([A-Za-z_]\w*)\b",
)
_ENDMODULE = re.compile(r"(?m)^\s*endmodule\b")
_INCLUDE = re.compile(r"^\s*`include\s+(?:\"([^\"]+)\"|<([^>]+)>)\s*$")
_kw = frozenset(
    {
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
        "posedge",
        "negedge",
        "edge",
        "fork",
        "join",
        "join_any",
        "join_none",
        "function",
        "task",
        "void",
        "automatic",
        "typedef",
        "enum",
        "struct",
        "union",
        "interface",
        "modport",
        "program",
        "package",
        "property",
        "sequence",
        "clocking",
        "covergroup",
        "final",
        "unique",
        "priority",
        "matches",
        "inside",
        "dist",
        "buf",
        "bufif0",
        "bufif1",
        "not",
        "and",
        "or",
        "nand",
        "nor",
        "xor",
        "xnor",
        "tran",
        "tranif0",
        "tranif1",
        "pullup",
        "pulldown",
        "module",
        "generate",
        "assign",
        "notif0",
        "notif1",
        "nmos",
        "pmos",
        "rnmos",
        "rpmos",
        "cmos",
        "rcmos",
        "tri",
        "tri0",
        "tri1",
        "triand",
        "trior",
        "trireg",
        "wand",
        "wor",
        "supply0",
        "supply1",
        "begin",
        "end",
        "else",
    }
)


def _consume_h_ws(s: str, i: int) -> int:
    """仅跳过水平空白，不把换行当空白吃掉（按行解析例化）。"""
    n = len(s)
    while i < n and s[i] in " \t":
        i += 1
    return i


def _skip_balanced_parens(s: str, i: int) -> int:
    """假定 s[i] == '('，返回与之匹配的 ')' 之后下标；若不配对则停在串末。"""
    n = len(s)
    if i >= n or s[i] != "(":
        return i
    depth = 0
    while i < n:
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return i


def parse_instance_line_analysis(line: str, self_mod: str) -> tuple[str | None, str]:
    """判断一行是否像模块例化；返回 (模块类型名或 None, 人类可读原因)。"""

    raw = line.strip()
    if not raw:
        return None, "空行或仅空白"
    if raw.startswith("`"):
        return None, "预处理指令行（不以例化解析）"
    if raw.startswith("//"):
        return None, "行注释残留（不应出现）"
    if raw.startswith("bind "):
        return None, "bind 行由单独规则处理"
    m_head = re.match(r"^([A-Za-z_]\w*)\b\s*", raw)
    if not m_head:
        return None, "行首不是标识符（不像 modtype …）"
    t = m_head.group(1)
    if t in _kw:
        return None, f"首标识符为关键字或内建门名 {t!r}，不当作模块类型"
    if t == self_mod:
        return None, f"首标识符与当前 module 名相同 {t!r}（避免自指）"
    i = _consume_h_ws(raw, m_head.end())
    if i < len(raw) and raw[i] == "#":
        i += 1
        i = _consume_h_ws(raw, i)
        if i >= len(raw) or raw[i] != "(":
            return None, "见 # 但后续不是 #( 形参列表，不像例化"
        i = _skip_balanced_parens(raw, i)
        i = _consume_h_ws(raw, i)
    if i < len(raw) and raw[i] == "(":
        i = _skip_balanced_parens(raw, i)
        i = _consume_h_ws(raw, i)
        if i < len(raw) and raw[i] == ";":
            return t, "匿名例化：modtype [#(…)] ( … );"
        return None, "括号后未以分号结束（可能是调用/表达式，不是例化）"
    m_inst = re.match(r"^([A-Za-z_]\w*)\b\s*\(", raw[i:])
    if not m_inst:
        return None, "#(…) 后无「实例名 (」形态，不像命名例化"
    inst = m_inst.group(1)
    if inst in _kw:
        return None, f"实例名位置为关键字 {inst!r}"
    return t, f"命名例化：modtype [#(…)] {inst} ( … );"


def _parse_module_instantiation(line: str, self_mod: str) -> str | None:
    """若本行像模块例化则返回被例化模块类型名，否则返回 None。"""
    t, _ = parse_instance_line_analysis(line, self_mod)
    return t


def _parse_bind_line(line: str) -> str | None:
    """解析 bind 行，返回被绑定模块类型名（非层次目标）。"""
    s = line.strip()
    if not s.startswith("bind "):
        return None
    m = re.match(r"^bind\s+([\w$.]+)\s+([A-Za-z_]\w*)\b\s*", s)
    if not m:
        return None
    mod_type = m.group(2)
    if mod_type in _kw:
        return None
    i = _consume_h_ws(s, m.end())
    if i < len(s) and s[i] == "#":
        i += 1
        i = _consume_h_ws(s, i)
        if i >= len(s) or s[i] != "(":
            return None
        i = _skip_balanced_parens(s, i)
        i = _consume_h_ws(s, i)
    m2 = re.match(r"^([A-Za-z_]\w*)\b\s*\(", s[i:])
    if not m2:
        return None
    if m2.group(1) in _kw:
        return None
    return mod_type


@dataclass
class VerilogSliceScan:
    defined_modules: list[str]
    referenced_modules: list[str]
    include_paths: list[str]


def _collect_refs_from_body(body: str, self_mod: str, refs: list[str]) -> None:
    for line in body.splitlines():
        hit = _parse_module_instantiation(line, self_mod)
        if hit:
            refs.append(hit)
        bh = _parse_bind_line(line)
        if bh:
            refs.append(bh)


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
        _collect_refs_from_body(body, name, refs)
        pos = end.end()
    for line in text.splitlines():
        bh = _parse_bind_line(line)
        if bh:
            refs.append(bh)
    if not defs:
        for im in _INCLUDE.finditer(text):
            p = im.group(1) or im.group(2) or ""
            if p:
                incs.append(p.strip())
        _collect_refs_from_body(text, "", refs)
    return VerilogSliceScan(
        defined_modules=sorted(set(defs)),
        referenced_modules=sorted(set(refs)),
        include_paths=sorted(set(incs)),
    )
