from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from alive_progress import alive_bar
from rich.console import Console

import impl  # noqa: F401  — 触发 sink 注册
from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="filelist-fix",
        description="从指定顶层模块出发收集 Verilog/SystemVerilog 依赖并生成 filelist。",
    )
    p.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.0.0",
    )
    p.add_argument(
        "sources",
        nargs="+",
        metavar="SOURCE",
        help="源码目录或可检索路径，可给多个。",
    )
    p.add_argument(
        "--top",
        "-t",
        dest="tops",
        action="append",
        default=[],
        required=True,
        help="顶层模块名，可重复给出多个。",
    )
    p.add_argument(
        "--prelude",
        "-p",
        dest="preludes",
        action="append",
        default=[],
        metavar="FILE",
        help="置于输出 filelist 最前的 filelist 或带 +define+ / +incdir+ 的片段，可多次指定并按顺序拼接。",
    )
    p.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        metavar="FILE",
        help="写出的 filelist 路径；省略则只打印到标准输出而不生成文件。",
    )
    p.add_argument(
        "--archive",
        type=Path,
        default=None,
        metavar="DB",
        help="SQLite 存档路径，用于按 mtime 缓存单文件解析结果以加速重复运行；省略则不开启。",
    )
    p.add_argument(
        "--log-file",
        type=Path,
        default=None,
        metavar="FILE",
        help="技术日志输出文件；省略则默认不写文件（仅依赖调试级别钩子）。",
    )
    p.add_argument(
        "--rg",
        type=Path,
        default=None,
        help="ripgrep 可执行文件路径，默认从 tools/bin 或 PATH 解析。",
    )
    p.add_argument(
        "--fd",
        type=Path,
        default=None,
        help="fd 可执行文件路径，默认从 tools/bin 或 PATH 解析。",
    )
    p.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="仓库根目录（含 tools/bin）；默认可从当前包位置推断。",
    )
    return p


def _configure_logging(path: Path | None) -> logging.Logger:
    log = logging.getLogger("filelist_fix")
    log.handlers.clear()
    log.propagate = False
    if path is None:
        log.addHandler(logging.NullHandler())
        log.setLevel(logging.WARNING)
        return log
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    log.setLevel(logging.DEBUG)
    return log


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    log = _configure_logging(args.log_file)
    console = Console(stderr=True)
    repo_root = args.repo_root.resolve() if args.repo_root else None

    with alive_bar(
        None,
        title="filelist",
        spinner="dots",
        monitor=False,
        stats=False,
    ) as bar:
        ctx = AppContext(logger=log, console=console, alive_bar=bar)
        app = FilelistApplication(
            search_roots=[Path(s) for s in args.sources],
            top_modules=args.tops,
            prelude_paths=[Path(f) for f in args.preludes],
            output_path=args.output,
            archive_path=args.archive,
            rg_path=args.rg,
            fd_path=args.fd,
            ctx=ctx,
            repo_root=repo_root,
        )
        rb = app.run()

    for line in rb.head_lines:
        console.print(line)
    for path_item in rb.ordered_paths:
        console.print(str(path_item))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
