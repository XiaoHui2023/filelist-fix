from __future__ import annotations

HD_SOURCE_EXTENSIONS: tuple[str, ...] = (
    "v",
    "sv",
    "vh",
    "svh",
    "vhd",
    "vhdl",
    "vp",
    "sva",
    "vams",
    "vl",
    "verilog",
)


def rg_include_globs() -> tuple[str, ...]:
    """供 ripgrep 的 --glob 使用，覆盖常见 HDL 源后缀（含 sv）。"""
    return tuple(f"*.{ext}" for ext in HD_SOURCE_EXTENSIONS)
