from __future__ import annotations

from api.resolve.verilog_text import (
    DropAlwaysishBlocksAPI,
    JoinContinuedLinesAPI,
    ScanVerilogForDependenciesAPI,
    StripVerilogCommentsAPI,
    SqueezeForDependencyScanAPI,
)
from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import (
    drop_alwaysish_blocks,
    join_continued_lines,
    squeeze_for_dependency_scan,
    strip_comments_preserve_strings,
)


@JoinContinuedLinesAPI.register
def resolve_join_continued_lines(cb: JoinContinuedLinesAPI) -> None:
    """Fold \\ line continuations before preprocessing."""
    cb.joined_text = join_continued_lines(cb.raw_text)


@StripVerilogCommentsAPI.register
def resolve_strip_comments(cb: StripVerilogCommentsAPI) -> None:
    """Strip comments while preserving strings."""
    cb.stripped_text = strip_comments_preserve_strings(cb.source_text)


@DropAlwaysishBlocksAPI.register
def resolve_drop_alwaysish(cb: DropAlwaysishBlocksAPI) -> None:
    """Remove always/initial/final blocks heuristically."""
    cb.dropped_text = drop_alwaysish_blocks(cb.source_text)


@SqueezeForDependencyScanAPI.register
def resolve_squeeze_for_dep_scan(cb: SqueezeForDependencyScanAPI) -> None:
    """Run the combined squeeze pipeline used before dependency regex."""
    cb.squeezed_text = squeeze_for_dependency_scan(cb.source_text)


@ScanVerilogForDependenciesAPI.register
def resolve_scan_verilog_for_deps(cb: ScanVerilogForDependenciesAPI) -> None:
    """Populate module/include scan fields from squeezed text."""
    r = scan_verilog_body(cb.scanned_text)
    cb.defined_modules = r.defined_modules
    cb.referenced_modules = r.referenced_modules
    cb.include_paths = r.include_paths
