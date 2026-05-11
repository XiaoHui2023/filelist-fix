from __future__ import annotations

import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.table import Column

import impl  # noqa: F401  — register sinks
from runtime.adaptive_bar_column import AdaptiveHueBarColumn
from runtime.cli_parser import build_parser, flatten_append_groups
from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication

# 进度条：HueBar（按完成比例红→黄→绿）；宽度参与描述列留白计算（含百分比列）。
_PROGRESS_BAR_WIDTH = 28
_PROGRESS_PCT_COL = Column(min_width=5, max_width=5, justify="right")


def _description_table_column(console: Console, bar_width: int) -> Column:
    """描述列宽度：按终端剩余宽度给足 ``max_width``，过长仍 ``ellipsis``（未写日志的详情在 -l）。"""
    w = console.width
    if w is None or w < 30:
        w = 80
    bw = max(1, int(bar_width))
    # spinner + 条形 + 百分比列 + 耗时 + 列间留白
    reserved = 3 + bw + 5 + 11 + 10
    desc_max = max(16, w - reserved)
    # 短终端时 min 不超过 max，避免 min_width>max_width
    min_w = min(52, desc_max)
    return Column(min_width=min_w, max_width=desc_max, overflow="ellipsis", no_wrap=True)


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
    sources = flatten_append_groups(args.sources)
    tops = flatten_append_groups(args.tops)
    preludes = flatten_append_groups(args.preludes)
    excludes = flatten_append_groups(args.excludes)
    log = _configure_logging(args.log_file)
    console = Console(stderr=True)
    elapsed_col = Column(min_width=11, max_width=11, justify="right")
    desc_col = _description_table_column(console, _PROGRESS_BAR_WIDTH)

    with Progress(
        SpinnerColumn("dots", style="progress.spinner"),
        TextColumn(
            "{task.description}",
            markup=True,
            justify="left",
            table_column=desc_col,
        ),
        AdaptiveHueBarColumn(bar_width=_PROGRESS_BAR_WIDTH),
        TaskProgressColumn(
            text_format="[grey70]{task.percentage:>3.0f}%[/grey70]",
            table_column=_PROGRESS_PCT_COL,
        ),
        TimeElapsedColumn(table_column=elapsed_col),
        console=console,
        transient=True,
        expand=True,
    ) as progress:
        tid = progress.add_task(
            "Starting...",
            total=max(1, len(tops)),
            completed=0,
        )
        ctx = AppContext(
            logger=log,
            console=console,
            rich_progress=progress,
            progress_task_id=tid,
        )
        app = FilelistApplication(
            search_roots=[Path(s) for s in sources],
            top_modules=tops,
            prelude_paths=[Path(f) for f in preludes],
            output_path=args.output,
            save_path=args.save,
            path_style=args.path_style,
            exclude_paths=[Path(x) for x in excludes],
            ctx=ctx,
        )
        rb = app.run()

    print(f"Wrote filelist: {args.output.resolve()}", file=sys.stderr)
    for name in rb.state.unresolved_modules:
        print(f'Warning: Not found module "{name}"', file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
