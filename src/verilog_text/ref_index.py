from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from verilog_text.scan import (
    _ENDMODULE,
    _MODULE_HEAD,
    _at_instance_scan_anchor,
    _consume_toplevel_semicolon_statement,
    _is_primitive_gate_type,
    _module_body_spans_by_stack,
    _package_names_in_import_statement,
    _parse_bind_line,
    _pos_in_any_span,
    _skip_sv_attribute_instances,
    _skip_ws_any,
    _split_package_regions_by_stack,
    _typedef_declaration_spans,
    _try_parse_module_instantiation_detail,
)

RefKind = Literal["instance", "bind", "import"]


@dataclass(frozen=True)
class ModuleRefSite:
    """一次进入闭包检索的模块/包引用位置（相对 scan 输入文本的行号）。"""

    referenced_module: str
    parent_module: str
    kind: RefKind
    line_in_scan_input: int
    instance_name: str | None = None
    excerpt: str = ""


def _line_number_at(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def _excerpt_at(text: str, index: int, *, limit: int = 160) -> str:
    line_start = text.rfind("\n", 0, index) + 1
    line_end = text.find("\n", index)
    if line_end < 0:
        line_end = len(text)
    raw = text[line_start:line_end].strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3] + "..."


def _collect_instance_sites_in_body(
    text: str,
    body: str,
    body_start: int,
    parent_module: str,
    out: list[ModuleRefSite],
) -> None:
    pos = 0
    n = len(body)
    td_spans = _typedef_declaration_spans(body)
    while pos < n:
        if _pos_in_any_span(pos, td_spans):
            pos += 1
            continue
        if _at_instance_scan_anchor(body, pos):
            hit = _try_parse_module_instantiation_detail(body, pos, parent_module)
            if hit:
                span, inst_name = hit
                if not _is_primitive_gate_type(span.mod_type):
                    abs_pos = body_start + _skip_ws_any(body, pos)
                    out.append(
                        ModuleRefSite(
                            referenced_module=span.mod_type,
                            parent_module=parent_module,
                            kind="instance",
                            instance_name=inst_name,
                            line_in_scan_input=_line_number_at(text, abs_pos),
                            excerpt=_excerpt_at(text, abs_pos),
                        )
                    )
                pos = hit[0].end
                continue
        pos += 1


def _collect_import_sites_in_body(
    text: str,
    body: str,
    body_start: int,
    parent_module: str,
    out: list[ModuleRefSite],
) -> None:
    i = _skip_ws_any(body, 0)
    while i < len(body):
        i = _skip_sv_attribute_instances(body, i)
        i = _skip_ws_any(body, i)
        if i >= len(body):
            break
        if i < len(body) - 1 and body[i : i + 2] == "#(":
            break
        if body[i] == "(" and not body.startswith("(*", i):
            break
        m = re.match(r"\bimport\b", body[i:])
        if not m:
            break
        stmt_start = i + m.start()
        stmt_body_start = i + m.end()
        stmt_end = _consume_toplevel_semicolon_statement(s=body, start=stmt_body_start)
        stmt = body[stmt_start:stmt_end]
        abs_pos = body_start + stmt_start
        for pkg in _package_names_in_import_statement(stmt):
            out.append(
                ModuleRefSite(
                    referenced_module=pkg,
                    parent_module=parent_module,
                    kind="import",
                    line_in_scan_input=_line_number_at(text, abs_pos),
                    excerpt=_excerpt_at(text, abs_pos),
                )
            )
        i = stmt_end


def _collect_bind_sites(text: str, out: list[ModuleRefSite]) -> None:
    for fi, line in enumerate(text.splitlines(), start=1):
        bh = _parse_bind_line(line)
        if bh and not _is_primitive_gate_type(bh):
            out.append(
                ModuleRefSite(
                    referenced_module=bh,
                    parent_module="",
                    kind="bind",
                    line_in_scan_input=fi,
                    excerpt=line.strip()[:160],
                )
            )


def collect_module_ref_sites(text: str) -> list[ModuleRefSite]:
    """从与 ``scan_verilog_body`` 相同的 scan 输入文本收集可检索的引用位置。"""

    out: list[ModuleRefSite] = []
    stacked = _module_body_spans_by_stack(text)
    if stacked is not None:
        for name, body_start, body_end in stacked:
            body = text[body_start:body_end]
            _collect_import_sites_in_body(text, body, body_start, name, out)
            _collect_instance_sites_in_body(text, body, body_start, name, out)
        pkg_search = 0
        for pname, pbody in _split_package_regions_by_stack(text):
            pkg_start = text.find(pbody, pkg_search)
            if pkg_start < 0:
                pkg_start = 0
            else:
                pkg_search = pkg_start + len(pbody)
            _collect_import_sites_in_body(text, pbody, pkg_start, pname, out)
            _collect_instance_sites_in_body(text, pbody, pkg_start, pname, out)
        _collect_bind_sites(text, out)
        return out

    pos = 0
    found_module = False
    while True:
        mh = _MODULE_HEAD.search(text, pos)
        if not mh:
            break
        found_module = True
        em = _ENDMODULE.search(text, mh.end())
        if not em:
            break
        name = mh.group(1)
        kbd = mh.end()
        body_start = kbd + 1 if kbd < len(text) and text[kbd] == "\n" else kbd
        body = text[body_start : em.start()]
        _collect_import_sites_in_body(text, body, body_start, name, out)
        _collect_instance_sites_in_body(text, body, body_start, name, out)
        pos = em.end()

    if not found_module:
        _collect_import_sites_in_body(text, text, 0, "", out)
        _collect_instance_sites_in_body(text, text, 0, "", out)

    pkg_search = 0
    for pname, pbody in _split_package_regions_by_stack(text):
        pkg_start = text.find(pbody, pkg_search)
        if pkg_start < 0:
            pkg_start = 0
        else:
            pkg_search = pkg_start + len(pbody)
        _collect_import_sites_in_body(text, pbody, pkg_start, pname, out)
        _collect_instance_sites_in_body(text, pbody, pkg_start, pname, out)

    _collect_bind_sites(text, out)
    return out


def format_module_ref_index(
    entries: list[tuple[str, str, ModuleRefSite]],
) -> str:
    """将多源引用记录格式化为单文件索引（按被引用名分组，便于搜索）。"""

    header = (
        "module_ref_index — 按被引用模块/包名汇总（--debug-dump 生成）\n"
        "\n"
        "用法：在本文件中搜索未找到的模块名（区分大小写）。\n"
        "line 指该源文件 by_file/<子目录>/03e_scan_input.txt 中的行号（与流水线 scan 输入一致）。\n"
        "同一物理源经 include 展平后，引用可能来自拼入的其它文件片段。\n"
        "\n"
    )
    if not entries:
        return header + "(本轮无引用记录；可能未解析任何源，或均未写 debug 片段。)\n"

    by_ref: dict[str, list[tuple[str, str, ModuleRefSite]]] = {}
    for source_path, scan_subdir, site in entries:
        by_ref.setdefault(site.referenced_module, []).append((source_path, scan_subdir, site))

    parts = [header]
    for ref_name in sorted(by_ref.keys()):
        parts.append("=" * 78 + "\n")
        parts.append(f"REFERENCED: {ref_name}\n")
        parts.append("=" * 78 + "\n\n")
        group = sorted(
            by_ref[ref_name],
            key=lambda t: (t[0], t[2].line_in_scan_input, t[2].parent_module, t[2].kind),
        )
        for source_path, scan_subdir, site in group:
            parts.append(f"  source_file: {source_path}\n")
            parts.append(f"  scan_input:  {scan_subdir}/03e_scan_input.txt\n")
            parent = site.parent_module if site.parent_module else "(file scope)"
            parts.append(f"  parent:      {parent}\n")
            parts.append(f"  kind:        {site.kind}\n")
            if site.instance_name:
                parts.append(f"  instance:    {site.instance_name}\n")
            elif site.kind == "instance":
                parts.append("  instance:    (anonymous)\n")
            parts.append(f"  line:        {site.line_in_scan_input}\n")
            if site.excerpt:
                parts.append(f"  excerpt:     {site.excerpt}\n")
            parts.append("\n")
    return "".join(parts)
