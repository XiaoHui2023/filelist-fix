from __future__ import annotations

from pathlib import Path

import impl  # noqa: F401 — register sinks

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_unresolved_modules_ordered_dedup(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "top.v").write_text(
        "module top();\n"
        "  missing_a u1();\n"
        "  missing_b u2();\n"
        "endmodule\n",
        encoding="utf-8",
    )
    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "out.f",
        save_path=None,
        ctx=ctx,
    )

    def fake_find(module: str, roots: object) -> Path | None:
        if module == "top":
            return src / "top.v"
        return None

    app._tools.find_file = fake_find

    rb = app.run()
    assert rb.state.unresolved_modules == ["missing_a", "missing_b"]
