from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from api.resolve.verilog_text import (
    JoinContinuedLinesAPI,
    ScanVerilogForDependenciesAPI,
    SqueezeForDependencyScanAPI,
)
from verilog_text.preproc import PreprocDirectiveParser
from verilog_text.scan import scan_verilog_body
from verilog_text.scan_trace import build_instance_scan_trace
from verilog_text.squeeze import (
    join_continued_lines,
    squeeze_for_dependency_scan,
    squeeze_pipeline_for_dependency_scan,
)

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
    ctx: Any | None = None,
) -> str:
    """在同一套预处理状态下展开可参与依赖分析的源码（含活动分支内的 `include）。"""
    if depth > 96:
        raise RecursionError("`include` nesting too deep (possible cycle or broken tree)")
    path = path.resolve()
    if path in stack:
        return ""
    stack.add(path)
    try:
        dbg = getattr(ctx, "dependency_debug_dump", None) if ctx is not None else None
        raw = path.read_text(encoding="utf-8", errors="replace")
        if ctx is not None:
            text = ctx.fire(JoinContinuedLinesAPI, raw_text=raw).joined_text
        else:
            text = join_continued_lines(raw)
        if dbg is not None:
            dbg.write_text(path, "01_joined.txt", text)
        chunks: list[str] = []
        for line in text.splitlines():
            if preproc.handle_directive_line(line):
                continue
            inc = _INCLUDE.match(line)
            if inc and preproc.line_is_active_source():
                target = inc.group(1) or inc.group(2) or ""
                child = resolve_include_path(target.strip(), path, incdirs)
                if child:
                    sub = flatten_active_text(child, preproc, incdirs, stack, depth + 1, ctx)
                    if sub:
                        chunks.append(sub)
                continue
            if preproc.line_is_active_source():
                chunks.append(line)
        out = "\n".join(chunks)
        if dbg is not None:
            dbg.write_text(path, "02_flatten_merged.txt", out)
        return out
    finally:
        stack.remove(path)


def extract_dependencies_from_file(
    path: Path,
    incdirs: list[Path],
    initial_defines: dict[str, str],
    *,
    ctx: Any | None = None,
) -> tuple[list[str], list[str], list[str]]:
    """返回该文件在宏环境下的已定义模块、引用模块与 include 路径串。"""
    pre = PreprocDirectiveParser(dict(initial_defines))
    flat = flatten_active_text(path, pre, incdirs, set(), 0, ctx)
    if ctx is not None:
        dbg = getattr(ctx, "dependency_debug_dump", None)
        if dbg is not None:
            stages = squeeze_pipeline_for_dependency_scan(flat)
            dbg.write_text(path, "03a_strip_comments.txt", stages[0])
            dbg.write_text(path, "03b_drop_alwaysish.txt", stages[1])
            dbg.write_text(path, "03c_strip_decl_noise.txt", stages[2])
            dbg.write_text(path, "03d0_pre_strip_module_ports.txt", stages[2])
            dbg.write_text(path, "03d_strip_module_ports.txt", stages[3])
            dbg.write_text(path, "03e_scan_input.txt", stages[4])
            dbg.write_text(
                path,
                "05_instance_scan_trace.txt",
                build_instance_scan_trace(stages[4]),
            )
        squ = ctx.fire(SqueezeForDependencyScanAPI, source_text=flat).squeezed_text
        if dbg is not None:
            assert squ == stages[4]
        r = ctx.fire(ScanVerilogForDependenciesAPI, scanned_text=squ)
        if dbg is not None:
            dbg.write_text(
                path,
                "04_scan_result.txt",
                "defined_modules: "
                + ", ".join(r.defined_modules)
                + "\nreferenced_modules: "
                + ", ".join(r.referenced_modules)
                + "\ninclude_paths: "
                + ", ".join(r.include_paths)
                + "\n",
            )
        return r.defined_modules, r.referenced_modules, r.include_paths
    squ = squeeze_for_dependency_scan(flat)
    scan = scan_verilog_body(squ)
    return scan.defined_modules, scan.referenced_modules, scan.include_paths
