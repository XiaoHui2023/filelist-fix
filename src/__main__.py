from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

import impl  # noqa: F401  — register sinks
from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="filelist-fix",
        description="Collect Verilog/SystemVerilog dependencies from top modules and emit a filelist.",
    )
    p.add_argument(
        "--source",
        "-s",
        dest="sources",
        action="append",
        default=[],
        metavar="PATH",
        required=True,
        help="Source root or file to search (repeatable).",
    )
    p.add_argument(
        "--top",
        "-t",
        dest="tops",
        action="append",
        default=[],
        required=True,
        help="Top-level module name (repeatable).",
    )
    p.add_argument(
        "--prelude",
        "-p",
        dest="preludes",
        action="append",
        default=[],
        metavar="FILE",
        help="Prelude file(s): +define+ / +incdir+ or plain lines prepended to output (repeatable, order preserved).",
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

    with Progress(
        SpinnerColumn("dots", style="progress.spinner"),
        TextColumn("{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        tid = progress.add_task("Starting...", total=None)
        ctx = AppContext(
            logger=log,
            console=console,
            rich_progress=progress,
            progress_task_id=tid,
        )
        app = FilelistApplication(
            search_roots=[Path(s) for s in args.sources],
            top_modules=args.tops,
            prelude_paths=[Path(f) for f in args.preludes],
            output_path=args.output,
            save_path=args.save,
            path_style=args.path_style,
            ctx=ctx,
        )
        rb = app.run()

    print(f"Wrote filelist: {args.output.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
