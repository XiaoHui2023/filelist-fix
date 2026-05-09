from pathlib import Path

import impl  # noqa: F401 — register sinks and resolve handlers

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication


def test_closure_smoke(tmp_path: Path) -> None:
    src = tmp_path / "src"
    src.mkdir()
    (src / "leaf.v").write_text(
        "module leaf();\nendmodule\n",
        encoding="utf-8",
    )
    (src / "top.v").write_text(
        "module top();\n  leaf u1();\nendmodule\n",
        encoding="utf-8",
    )
    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[src],
        top_modules=["top"],
        prelude_paths=[],
        output_path=tmp_path / "closure.f",
        save_path=None,
        ctx=ctx,
    )
    hits = {"top": src / "top.v", "leaf": src / "leaf.v"}
    app._tools.find_file = lambda m, *_: hits.get(m)

    rb = app.run()
    paths = {p.resolve() for p in rb.ordered_paths}
    assert (src / "leaf.v").resolve() in paths
    assert (src / "top.v").resolve() in paths

    text = (tmp_path / "closure.f").read_text(encoding="utf-8")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    assert lines == ["src/leaf.v", "src/top.v"]
