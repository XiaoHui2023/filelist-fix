from __future__ import annotations

import re

from verilog_text.scan import (
    _consume_h_ws,
    _ENDMODULE,
    _MODULE_HEAD,
    _skip_balanced_parens,
    skeletonize_scanned_verilog_for_dependency_scan,
)

_BLOCK_COM = re.compile(r"/\*.*?\*/", re.DOTALL)
_LINE_COM = re.compile(r"//.*?$", re.MULTILINE)
_STR_DQ = re.compile(r'"([^"\\]|\\.)*"')
# Verilog / SystemVerilog sized literals (e.g. 4'd1, 16'sh0, 5'ha). Replaced with the
# same-length run of spaces (not deleted) before _STR_SQ so adjacent literals are not
# parsed as one '…' span; spaces keep token boundaries—do not use '_' here or
# identifiers could merge (e.g. a_4'd1_b → a_____b as one token).
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
# case / endcase：与 begin/end 一起在 always 等过程块内配对。
_CASE_LINE = re.compile(
    r"^\s*(?:(?:unique|priority)\s+)?(?:randcase|casez|casex|case)\b",
)
_ENDCASE_LINE = re.compile(r"^\s*endcase\b")
_TASK_HEAD = re.compile(
    r"^\s*(?:(?:pure\s+virtual|virtual|static|automatic)\s+)*task\b",
)
_ENDTASK_HEAD = re.compile(r"^\s*endtask\b")
_EXTERN_TASK_HEAD = re.compile(r"^\s*extern\s+task\b")
_SPECIFY_HEAD = re.compile(r"^\s*specify\b")
_ENDSPECIFY_HEAD = re.compile(r"^\s*endspecify\b")
# 行首可选 ``label :``；块内 case/if/begin 等由整段丢弃覆盖，无需单独配对。
_GENERATE_HEAD = re.compile(r"^\s*(?:[A-Za-z_]\w*\s*:\s*)?generate\b")
_ENDGENERATE_HEAD = re.compile(r"^\s*endgenerate\b")


def strip_comments_preserve_strings(src: str) -> str:
    """去掉块注释与行注释，尽量不把字符串里的 // 误判为注释。

    双引号串先整体空白化；再将位宽进制字面量（如 **4'd1**、**5'ha**）替换为**等长空白**
    （保留字符总数与括号配对，不是删空），以免下一步对成对单引号的处理把相邻字面量
    误并成一段；最后处理成对单引号串。
    """

    def _blank_dq(m: re.Match[str]) -> str:
        return '"' + " " * (len(m.group(0)) - 2) + '"'

    def _blank_sq(m: re.Match[str]) -> str:
        return "'" + " " * (len(m.group(0)) - 2) + "'"

    def _blank_sized_literal(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    t = _STR_DQ.sub(_blank_dq, src)
    t = _SIZED_LITERAL.sub(_blank_sized_literal, t)
    t = _STR_SQ.sub(_blank_sq, t)
    t = _BLOCK_COM.sub(lambda mm: " " * len(mm.group(0)), t)
    t = _LINE_COM.sub("", t)
    return t


def drop_alwaysish_blocks(src: str) -> str:
    """去掉与例化无关的过程性整块，减轻后续依赖扫描的正则工作量（启发式）。

    含 **always / always_ff / always_comb / always_latch**、**initial**、**final**（按
    ``begin``/``end`` 与 ``case``/``endcase`` 嵌套计数吞整块；首行无 ``begin`` 时不再仅用首遇分号结束），以及 **task…endtask**、**extern task** 原型、
    **specify…endspecify**、**generate…endgenerate**（按 generate 嵌套深度整段丢弃，
    块内 case/if/begin 等不必单独解析）。**generate 体内的例化不再参与依赖抽取**。
    """
    lines = src.splitlines(True)
    out: list[str] = []
    i = 0
    n = len(lines)
    trigger = re.compile(r"^\s*(always(?:_(?:ff|comb|latch))?|initial|final)\b")
    task_depth = 0
    specify_depth = 0
    generate_depth = 0

    def skip_extern_task_proto(j: int) -> int:
        """跳过 ``extern task`` 原型（无 ``endtask``），直到形参表闭合后的分号。"""
        k = j
        depth = 0
        seen_lp = False
        pending_semi = False
        while k < n:
            s = lines[k]
            for ch in s:
                if pending_semi:
                    if ch == ";":
                        return k + 1
                elif ch == "(":
                    depth += 1
                    seen_lp = True
                elif ch == ")":
                    if depth > 0:
                        depth -= 1
                    if depth == 0 and seen_lp:
                        pending_semi = True
            if pending_semi and ";" in s:
                return k + 1
            if not seen_lp and ";" in s:
                return k + 1
            k += 1
        return k

    while i < n:
        line = lines[i]

        if task_depth > 0:
            if _ENDTASK_HEAD.match(line):
                task_depth -= 1
            elif _TASK_HEAD.match(line):
                task_depth += 1
            i += 1
            continue

        if specify_depth > 0:
            if _ENDSPECIFY_HEAD.match(line):
                specify_depth -= 1
            elif _SPECIFY_HEAD.match(line):
                specify_depth += 1
            i += 1
            continue

        if generate_depth > 0:
            if _ENDGENERATE_HEAD.match(line):
                generate_depth -= 1
            elif _GENERATE_HEAD.match(line):
                generate_depth += 1
            i += 1
            continue

        if _EXTERN_TASK_HEAD.match(line):
            i = skip_extern_task_proto(i)
            continue

        if trigger.match(line):
            i = _consume_always_initial_final_block(lines, i, n)
            continue

        if _TASK_HEAD.match(line):
            task_depth = 1
            i += 1
            continue

        if _SPECIFY_HEAD.match(line):
            specify_depth = 1
            i += 1
            continue

        if _GENERATE_HEAD.match(line):
            generate_depth = 1
            i += 1
            continue

        out.append(line)
        i += 1
    return "".join(out)


def _line_has_top_level_semicolon(s: str) -> bool:
    """行内是否存在处于 ``()``/``[]``/``{}`` 最外层的分号（用于多行 parameter / 单行 always 结束判定）。"""
    p = br = bc = 0
    for ch in s:
        if ch == "(":
            p += 1
        elif ch == ")":
            if p > 0:
                p -= 1
        elif ch == "[":
            br += 1
        elif ch == "]":
            if br > 0:
                br -= 1
        elif ch == "{":
            bc += 1
        elif ch == "}":
            if bc > 0:
                bc -= 1
        elif ch == ";" and p == 0 and br == 0 and bc == 0:
            return True
    return False


def _consume_always_initial_final_block(lines: list[str], start: int, n: int) -> int:
    """从 ``always``/``initial``/``final`` 的 trigger 行起吞整块（``begin``/``end`` 与 ``case``/``endcase`` 嵌套）。"""
    i = start
    depth = 0
    case_d = 0
    saw_structure = False
    while i < n:
        cur = lines[i]
        depth += len(_BEGIN.findall(cur)) - len(_END.findall(cur))
        if _CASE_LINE.match(cur):
            case_d += 1
        if _ENDCASE_LINE.match(cur):
            case_d -= 1
        if depth > 0 or case_d > 0:
            saw_structure = True
        elif i > start and cur.strip():
            saw_structure = True
        i += 1
        if i == start + 1 and _line_has_top_level_semicolon(lines[start]):
            break
        if depth <= 0 and case_d <= 0 and i > start + 1 and (saw_structure or cur.strip()):
            break
    return i


_NOISE_LINE = re.compile(
    r"^\s*(?:assign|"
    r"input|output|inout|ref|"
    r"wire|trireg|tri[01]?|tri|wand|wor|reg|logic|bit|"
    r"int(?:eger)?|shortint|longint|byte|real|time)\b",
)
# localparam / parameter 可能跨多行逗号续写，见 strip_decl_noise_lines 专支。
_PARAM_MULTILINE_HEAD = re.compile(r"^\s*(?:localparam|localparameter|parameter)\b")
# 文件级或 module 体内的编译指令行；整行去掉以免时间单位名等干扰跨行例化扫描。
_DIRECTIVE_NOISE_LINE = re.compile(
    r"^\s*`(?:timescale|celldefine|endcelldefine)\b",
)


def strip_decl_noise_lines(src: str) -> str:
    """按行去掉 assign、parameter/localparam（含多行逗号续写直至顶层分号）、port 方向等声明及若干编译指令行，减轻例化误匹配（启发式）。"""

    def _blank_line(line: str) -> str:
        if line.endswith("\r\n"):
            return "\r\n"
        if line.endswith("\n"):
            return "\n"
        return "\n"

    lines = src.splitlines(keepends=True)
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if _PARAM_MULTILINE_HEAD.match(line):
            while i < n:
                cur = lines[i]
                out.append(_blank_line(cur))
                if _line_has_top_level_semicolon(cur):
                    i += 1
                    break
                i += 1
            continue
        if _NOISE_LINE.match(line) or _DIRECTIVE_NOISE_LINE.match(line):
            out.append(_blank_line(line))
        else:
            out.append(line)
        i += 1
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

    各步按顺序去掉「与例化无关」的噪声，使后续正则只在更短、更干净的文本上工作：

    Returns:
        (strip_comments, drop_alwaysish, strip_decl_noise, strip_module_ports, scan_input).

        #. **strip_comments**：注释与串内形状处理，避免误匹配。
        #. **drop_alwaysish**：``always``/``initial``/``final``、``task``、``specify``、``generate`` 等整块。
        #. **strip_decl_noise**：assign、parameter、port 方向、wire、若干 `` ` `` 编译指令行。
        #. **strip_module_ports**：各 module 体内去掉端口头。
        #. **scan_input**：已识别例化的端口表内置空白，再送入 ``scan_verilog_body``。
    """

    a = strip_comments_preserve_strings(src)
    b = drop_alwaysish_blocks(a)
    c = strip_decl_noise_lines(b)
    d = strip_module_port_regions(c)
    e = skeletonize_scanned_verilog_for_dependency_scan(d)
    return a, b, c, d, e


def squeeze_for_dependency_scan(src: str) -> str:
    """按固定顺序压缩文本，去掉与例化无关的干扰后再做端口剥离与例化端口骨架化。

    顺序为：去注释 → 去过程块（含 **always** 全家、**task**、**specify**、**generate…endgenerate** 等；
    **generate** 体内例化不再抽取）→ 声明/指令行噪声 → module 端口头 → 端口表空白化；输出供 ``scan_verilog_body`` 使用。
    """
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
