from __future__ import annotations

import re
from pathlib import Path

from runtime.log_format import lines_block
from runtime.logging_setup import configure_cli_logging


def test_lines_block_empty() -> None:
    assert lines_block("items", []) == "items: (none)"


def test_lines_block_multiline() -> None:
    s = lines_block("mods", ["a", "b"])
    assert s == "mods (2):\n  - a\n  - b"


def test_configure_cli_logging_overwrites_file(tmp_path: Path) -> None:
    p = tmp_path / "run.log"
    configure_cli_logging(p).info("first_run_marker")
    configure_cli_logging(p).info("second_only")
    text = p.read_text(encoding="utf-8")
    assert "first_run_marker" not in text
    assert "second_only" in text


def test_log_lines_have_no_iso_date_prefix(tmp_path: Path) -> None:
    p = tmp_path / "x.log"
    configure_cli_logging(p).info("marker_only")
    text = p.read_text(encoding="utf-8")
    assert "marker_only" in text
    first = text.splitlines()[0]
    assert not re.search(r"\d{4}-\d{2}-\d{2}", first), first
    assert first.startswith(("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")), first
