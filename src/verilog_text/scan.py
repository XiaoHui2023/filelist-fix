from __future__ import annotations

import re
from dataclasses import dataclass

_ANCHOR_BEFORE_INSTANCE = frozenset(
    {
        "begin",
        "end",
        "else",
        "endgenerate",
        "endcase",
        "generate",
        "case",
        "casex",
        "casez",
        "default",
        "for",
        "foreach",
        "while",
        "repeat",
        "do",
        "if",
        "wait",
        "forever",
        "unique",
        "priority",
        "final",
        "always",
        "always_ff",
        "always_comb",
        "initial",
        "specify",
        "endspecify",
    }
)
_ID_HEAD = re.compile(r"([A-Za-z_]\w*)\b")

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


def _skip_ws_any(s: str, i: int) -> int:
    """跳过各类空白（含换行），用于跨行例化形态。"""
    n = len(s)
    while i < n and s[i] in " \t\n\r\v\f":
        i += 1
    return i


def _word_ending_at(s: str, j: int) -> str | None:
    """若 ``s[j]`` 落在标识符尾上，返回该标识符全文，否则返回 None。"""
    if j < 0 or j >= len(s) or not (s[j].isalnum() or s[j] == "_"):
        return None
    hi = j
    while hi + 1 < len(s) and (s[hi + 1].isalnum() or s[hi + 1] == "_"):
        hi += 1
    lo = j
    while lo - 1 >= 0 and (s[lo - 1].isalnum() or s[lo - 1] == "_"):
        lo -= 1
    return s[lo : hi + 1]


def _at_instance_scan_anchor(s: str, pos: int) -> bool:
    """仅在「像新语句起点」处尝试例化，避免把 ``u1`` 当成模块类型误扫。"""
    if pos == 0:
        return True
    j = pos - 1
    while j >= 0 and s[j] in " \t\r\v\f":
        j -= 1
    if j < 0:
        return True
    if s[j] == "\n":
        return True
    if s[j] in ";{}():":
        return True
    w = _word_ending_at(s, j)
    return w is not None and w in _ANCHOR_BEFORE_INSTANCE


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


@dataclass(frozen=True)
class _ModuleInstSpan:
    """一次成功识别的例化：模块类型名、分号后下标、最外层端口表括号范围。"""

    mod_type: str
    end: int
    port_open: int
    port_close_excl: int


def _try_parse_module_instantiation_span(s: str, pos: int, self_mod: str) -> _ModuleInstSpan | None:
    """从 ``pos`` 起解析命名/匿名例化至结束分号；失败返回 None。"""
    n = len(s)
    i = _skip_ws_any(s, pos)
    m = _ID_HEAD.match(s, i)
    if not m:
        return None
    t = m.group(1)
    if t in _kw or t == self_mod:
        return None
    i = _skip_ws_any(s, m.end())
    if i < n and s[i] == "#":
        i += 1
        i = _skip_ws_any(s, i)
        if i >= n or s[i] != "(":
            return None
        i = _skip_balanced_parens(s, i)
        i = _skip_ws_any(s, i)
    if i < n and s[i] == "(":
        port_open = i
        i = _skip_balanced_parens(s, i)
        port_close_excl = i
        i = _skip_ws_any(s, i)
        if i >= n or s[i] != ";":
            return None
        return _ModuleInstSpan(t, i + 1, port_open, port_close_excl)
    m2 = _ID_HEAD.match(s, i)
    if not m2:
        return None
    inst = m2.group(1)
    if inst in _kw:
        return None
    i = _skip_ws_any(s, m2.end())
    if i >= n or s[i] != "(":
        return None
    port_open = i
    i = _skip_balanced_parens(s, i)
    port_close_excl = i
    i = _skip_ws_any(s, i)
    if i >= n or s[i] != ";":
        return None
    return _ModuleInstSpan(t, i + 1, port_open, port_close_excl)


def _collect_instance_refs_span_scan(body: str, self_mod: str, refs: list[str]) -> None:
    """跨行例化：仅在锚点处尝试解析，避免实例名被当成模块类型。"""
    pos = 0
    n = len(body)
    while pos < n:
        if _at_instance_scan_anchor(body, pos):
            hit = _try_parse_module_instantiation_span(body, pos, self_mod)
            if hit:
                refs.append(hit.mod_type)
                pos = hit.end
                continue
        pos += 1


def skeletonize_body_instance_ports(body: str, self_mod: str) -> str:
    """将本段内已识别例化的最外层端口括弧内部换成空白，便于基于行的检索且不改变括号层级。"""
    spans: list[_ModuleInstSpan] = []
    pos = 0
    n = len(body)
    while pos < n:
        if _at_instance_scan_anchor(body, pos):
            hit = _try_parse_module_instantiation_span(body, pos, self_mod)
            if hit:
                spans.append(hit)
                pos = hit.end
                continue
        pos += 1
    out = body
    for sp in reversed(spans):
        lo = sp.port_open + 1
        hi = sp.port_close_excl - 1
        if lo < hi:
            out = out[:lo] + (" " * (hi - lo)) + out[hi:]
    return out


def skeletonize_scanned_verilog_for_dependency_scan(text: str) -> str:
    """按 module…endmodule 分段，对各段体内做 ``skeletonize_body_instance_ports``。"""
    pieces: list[str] = []
    pos = 0
    while True:
        mh = _MODULE_HEAD.search(text, pos)
        if not mh:
            tail = text[pos:]
            if tail:
                pieces.append(skeletonize_body_instance_ports(tail, ""))
            break
        pieces.append(text[pos : mh.end()])
        em = _ENDMODULE.search(text, mh.end())
        if not em:
            pieces.append(skeletonize_body_instance_ports(text[mh.end() :], mh.group(1)))
            break
        name = mh.group(1)
        body = text[mh.end() : em.start()]
        pieces.append(skeletonize_body_instance_ports(body, name))
        pieces.append(text[em.start() : em.end()])
        pos = em.end()
    return "".join(pieces)


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
    _collect_instance_refs_span_scan(body, self_mod, refs)
    for line in body.splitlines():
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
