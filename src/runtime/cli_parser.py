from __future__ import annotations

import argparse
from pathlib import Path


def flatten_append_groups(groups: list[list[str]] | None) -> list[str]:
    """把 `nargs='+'` + `action='append'` 得到的若干组压成一层，顺序不变。"""
    if not groups:
        return []
    out: list[str] = []
    for g in groups:
        out.extend(g)
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="filelist-fix",
        description="Collect Verilog/SystemVerilog dependencies from top modules and emit a filelist.",
    )
    p.add_argument(
        "--source",
        "-s",
        dest="sources",
        nargs="+",
        action="append",
        default=[],
        metavar="PATH",
        required=True,
        help="Source root or file to search (repeatable; multiple paths may follow one -s).",
    )
    p.add_argument(
        "--exclude",
        "-x",
        dest="excludes",
        nargs="+",
        action="append",
        default=[],
        metavar="PATH",
        help="Exclude file(s) or directory tree(s) from search under --source (repeatable; multiple paths may follow one -x). Path must exist.",
    )
    p.add_argument(
        "--top",
        "-t",
        dest="tops",
        nargs="+",
        action="append",
        default=[],
        required=True,
        help="Top-level module name (repeatable; multiple names may follow one -t).",
    )
    p.add_argument(
        "--prelude",
        "-p",
        dest="preludes",
        nargs="+",
        action="append",
        default=[],
        metavar="FILE",
        help="Prelude file(s): +define+ / +incdir+ or plain lines prepended to output (repeatable, order preserved; multiple files may follow one -p).",
    )
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        metavar="FILE",
        help="Write filelist to this path (prelude lines then ordered paths).",
    )
    p.add_argument(
        "--save",
        type=Path,
        default=None,
        metavar="FILE",
        help="SQLite file for per-file parse cache; reuse when sources unchanged (mtime/size). Omit to disable. A .db suffix is typical.",
    )
    p.add_argument(
        "--path-style",
        choices=("relative", "absolute"),
        default="relative",
        help="How to write source paths in the filelist body: relative to the output file's directory (default), or absolute. Prelude lines are unchanged.",
    )
    p.add_argument(
        "--log",
        "-l",
        type=Path,
        default=None,
        metavar="FILE",
        dest="log_file",
        help="Log file. Omit for no file logging (debug hooks only).",
    )
    p.add_argument(
        "--debug-dump",
        type=Path,
        default=None,
        metavar="DIR",
        dest="debug_dump",
        help="Write per-source dependency pipeline stages under DIR (README.txt explains). No relation to -l.",
    )
    return p
