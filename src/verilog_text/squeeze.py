from __future__ import annotations

import re

_BLOCK_COM = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COM = re.compile(r"//.*?$", re.MULTILINE)
_STR_DQ = re.compile(r'"([^"\\]|\\.)*"')
_STR_SQ = re.compile(r"'([^'\\]|\\.)*'")
_BEGIN = re.compile(r"\bbegin\b")
_END = re.compile(r"\bend\b")


def strip_comments_preserve_strings(src: str) -> str:
    """去掉块注释与行注释，尽量不把字符串里的 // 误判为注释。"""

    def _blank_dq(m: re.Match[str]) -> str:
        return '"' + " " * (len(m.group(0)) - 2) + '"'

    def _blank_sq(m: re.Match[str]) -> str:
        return "'" + " " * (len(m.group(0)) - 2) + "'"

    t = _STR_DQ.sub(_blank_dq, src)
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


def squeeze_for_dependency_scan(src: str) -> str:
    """组合去注释与过程块删除，得到更适合做模块级正则扫描的文本。"""
    s = strip_comments_preserve_strings(src)
    s = drop_alwaysish_blocks(s)
    return s


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
