from __future__ import annotations

import re
from pathlib import Path

from core.vlog_preproc import PreprocDirectiveParser
from core.vlog_scan import scan_verilog_body
from core.vlog_squeeze import join_continued_lines, squeeze_for_dependency_scan

_INCLUDE = re.compile(r"^\s*`include\s+(?:\"([^\"]+)\"|<([^>]+)>)\s*(//.*)?$")


def resolve_include_path(rel: str, current_file: Path, incdirs: list[Path]) -> Path | None:
    """按当前文件目录与 incdir 列表解析 `include 目标。"""
    rel_p = Path(rel)
    cand = (current_file.parent / rel_p).resolve()
    if cand.is_file():
        return cand
    for d in incdirs:
        c2 = (d / rel_p).resolve()
        if c2.is_file():
            return c2
    return None


def flatten_active_text(
    path: Path,
    preproc: PreprocDirectiveParser,
    incdirs: list[Path],
    stack: set[Path],
    depth: int,
) -> str:
    """在同一套预处理状态下展开可参与依赖分析的源码（含活动分支内的 `include）。"""
    if depth > 96:
        raise RecursionError("include 嵌套过深，可能存在环或异常工程结构")
    path = path.resolve()
    if path in stack:
        return ""
    stack.add(path)
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
        text = join_continued_lines(raw)
        chunks: list[str] = []
        for line in text.splitlines():
            if preproc.handle_directive_line(line):
                continue
            inc = _INCLUDE.match(line)
            if inc and preproc.line_is_active_source():
                target = inc.group(1) or inc.group(2) or ""
                child = resolve_include_path(target.strip(), path, incdirs)
                if child:
                    sub = flatten_active_text(child, preproc, incdirs, stack, depth + 1)
                    if sub:
                        chunks.append(sub)
                continue
            if preproc.line_is_active_source():
                chunks.append(line)
        return "\n".join(chunks)
    finally:
        stack.remove(path)


def extract_dependencies_from_file(
    path: Path,
    incdirs: list[Path],
    initial_defines: dict[str, str],
) -> tuple[list[str], list[str], list[str]]:
    """返回该文件在宏环境下的已定义模块、引用模块与 include 路径串。"""
    pre = PreprocDirectiveParser(dict(initial_defines))
    flat = flatten_active_text(path, pre, incdirs, set(), 0)
    squ = squeeze_for_dependency_scan(flat)
    scan = scan_verilog_body(squ)
    return scan.defined_modules, scan.referenced_modules, scan.include_paths
