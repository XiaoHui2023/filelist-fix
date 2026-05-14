from __future__ import annotations

import re

from verilog_text.scan import _consume_h_ws, _ENDMODULE, _MODULE_HEAD, _skip_balanced_parens

_BLOCK_COM = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COM = re.compile(r"//.*?$", re.MULTILINE)
_STR_DQ = re.compile(r'"([^"\\]|\\.)*"')
# Verilog / SystemVerilog sized literals (e.g. 4'd1, 16'sh0, 5'ha) — must run
# before _STR_SQ so a pair of literals is not misread as one '…' string.
_SIZED_LITERAL = re.compile(
    r"(?<![\w$])(?:\d+)?'[sS]?(?:"
    r"[bB][01_xzXZ?]+|"
    r"[oO][0-7_xzXZ?]+|"
    r"[dD][0-9_?]+|"
    r"[hH][0-9a-fA-F_xzXZ?]+"
    r")(?![\w$])",
)
_STR_SQ = re.compile(r"'([^'\\]|\\.)*'")
_BEGIN = re.compile(r"\bbegin\b")
_END = re.compile(r"\bend\b")


def strip_comments_preserve_strings(src: str) -> str:
    """去掉块注释与行注释，尽量不把字符串里的 // 误判为注释。

    双引号串先整体空白化；再空白化 Verilog/SV 位宽进制字面量（如 4'd1、5'ha），
    以免后续对成对单引号的处理把相邻字面量误并成一段；最后处理成对单引号串。
    """

    def _blank_dq(m: re.Match[str]) -> str:
        return '"' + " " * (len(m.group(0)) - 2) + '"'

    def _blank_sq(m: re.Match[str]) -> str:
        return "'" + " " * (len(m.group(0)) - 2) + "'"

    def _blank_len(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    t = _STR_DQ.sub(_blank_dq, src)
    t = _SIZED_LITERAL.sub(_blank_len, t)
    t = _STR_SQ.sub(_blank_sq, t)
    t = _BLOCK_COM.sub(lambda mm: " " * len(mm.group(0)), t)
    t = _LINE_COM.sub("", t)
    return t


def drop_alwaysish_blocks(src: str) -> str:
    """删除 always/initial/final 等过程块，降低后续依赖扫描的正则成本（启发式）。"""
    lines = src.splitlines(True)
    out: list[str] = []
    i = 0
    n = len(lines)
    trigger = re.compile(r"^\s*(always(?:_ff|_comb)?|initial|final)\b")
    while i < n:
        line = lines[i]
        if not trigger.match(line):
            out.append(line)
            i += 1
            continue
        if _BEGIN.search(line):
            depth = len(_BEGIN.findall(line)) - len(_END.findall(line))
            i += 1
            while i < n:
                depth += len(_BEGIN.findall(lines[i]))
                depth -= len(_END.findall(lines[i]))
                i += 1
                if depth <= 0:
                    break
        else:
            while i < n and ";" not in lines[i]:
                i += 1
            i += 1
    return "".join(out)


_NOISE_LINE = re.compile(
    r"^\s*(?:assign|localparam|localparameter|parameter|"
    r"wire|trireg|tri[01]?|tri|wand|wor|reg|logic|bit|"
    r"int(?:eger)?|shortint|longint|byte|real|time)\b",
)


def strip_decl_noise_lines(src: str) -> str:
    """按行去掉 assign / localparam / wire 等声明，减轻例化行误匹配（启发式，单行）。"""

    def _blank_line(line: str) -> str:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
        return "\n"

    out: list[str] = []
    for line in src.splitlines(keepends=True):
        if _NOISE_LINE.match(line):
            out.append(_blank_line(line))
        else:
            out.append(line)
    return "".join(out)


def _skip_leading_ws_nl(s: str, i: int) -> int:
    n = len(s)
    while i < n and s[i] in " \t\n\r\v\f":
        i += 1
    return i


def _strip_module_body_header_prefix(body: str) -> str:
    """去掉 module 名之后、endmodule 之前的 #(…) 与 (…) 端口表及收尾分号。"""

    i = _skip_leading_ws_nl(body, 0)
    n = len(body)
    if i < n and body[i] == "#":
        i += 1
        i = _consume_h_ws(body, i)
        if i < n and body[i] == "(":
            i = _skip_balanced_parens(body, i)
        i = _skip_leading_ws_nl(body, i)
    if i < n and body[i] == "(":
        i = _skip_balanced_parens(body, i)
        i = _skip_leading_ws_nl(body, i)
    if i < n and body[i] == ";":
        i += 1
    return body[i:]


def strip_module_port_regions(text: str) -> str:
    """在每个 module…endmodule 体内去掉端口头，仅保留参与例化扫描的体文本。"""

    pieces: list[str] = []
    pos = 0
    while True:
        mh = _MODULE_HEAD.search(text, pos)
        if not mh:
            pieces.append(text[pos:])
            break
        pieces.append(text[pos : mh.end()])
        em = _ENDMODULE.search(text, mh.end())
        if not em:
            pieces.append(text[mh.end() :])
            break
        body = text[mh.end() : em.start()]
        pieces.append(_strip_module_body_header_prefix(body))
        pieces.append(text[em.start() : em.end()])
        pos = em.end()
    return "".join(pieces)


def squeeze_pipeline_for_dependency_scan(
    src: str,
) -> tuple[str, str, str, str, str]:
    """与 ``squeeze_for_dependency_scan`` 相同的各步中间结果，供调试写出。

    Returns:
        (strip_comments, drop_alwaysish, strip_decl_noise, strip_module_ports, scan_input).
    """

    a = strip_comments_preserve_strings(src)
    b = drop_alwaysish_blocks(a)
    c = strip_decl_noise_lines(b)
    d = strip_module_port_regions(c)
    return a, b, c, d, d


def squeeze_for_dependency_scan(src: str) -> str:
    """组合去注释、过程块删除、声明噪声与 module 端口前缀剥离，得到依赖扫描输入。"""
    return squeeze_pipeline_for_dependency_scan(src)[-1]


def join_continued_lines(text: str) -> str:
    """把行尾的反斜杠续行折成单行，保证预处理与 `define 观感一致。"""
    lines: list[str] = []
    buf = ""
    for raw in text.splitlines():
        if buf:
            buf = buf[:-1] + raw.lstrip()
        else:
            buf = raw
        if raw.rstrip().endswith("\\") and not raw.rstrip().endswith("\\\\"):
            continue
        lines.append(buf)
        buf = ""
    if buf:
        lines.append(buf)
    return "\n".join(lines)
