from __future__ import annotations

import logging
from pathlib import Path


def configure_cli_logging(path: Path | None) -> logging.Logger:
    """为 CLI 配置 filelist_fix 日志器：写文件时为 DEBUG；每次运行覆盖文件且行首不写日期时间。"""

    log = logging.getLogger("filelist_fix")
    log.handlers.clear()
    log.propagate = False
    if path is None:
        log.addHandler(logging.NullHandler())
        log.setLevel(logging.WARNING)
        return log
    fh = logging.FileHandler(path, mode="w", encoding="utf-8")
    fh.setFormatter(
        logging.Formatter(fmt="%(levelname)-7s | %(message)s"),
    )
    log.addHandler(fh)
    log.setLevel(logging.DEBUG)
    return log
