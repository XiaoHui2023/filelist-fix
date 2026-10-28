from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from runtime.context import AppContext
from runtime.filelist_app import FilelistApplication
from verilog_text.scan import scan_verilog_body
from verilog_text.squeeze import squeeze_for_dependency_scan


def build(tmp_path: Path, preludes: list[Path] = (), *, save: bool = False):
    ctx = AppContext(logger=None, console=None)
    app = FilelistApplication(
        search_roots=[tmp_path], top_modules=["top"], prelude_paths=list(preludes),
        output_path=tmp_path / "out.f", save_path=tmp_path / "cache.db" if save else None,
        ctx=ctx,
    )
    return app.run(), ctx


def write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_prelude_source_is_emitted_once(tmp_path: Path):
    leaf = write(tmp_path, "leaf.sv", "module leaf;\nendmodule\n")
    write(tmp_path, "top.sv", "module top;\nleaf u();\nendmodule\n")
    rb, ctx = build(tmp_path, [leaf])
    assert rb is not None and not ctx.exit_code
    assert (tmp_path / "out.f").read_text().splitlines().count("leaf.sv") == 1


@pytest.mark.parametrize("save", [False, True])
def test_prelude_macros_select_dependency(tmp_path: Path, save: bool):
    defs = write(tmp_path, "defs.svh", "`define PICK\n")
    write(tmp_path, "top.sv", "module top;\n`ifdef PICK\nchosen u();\n`else\nother u();\n`endif\nendmodule\n")
    write(tmp_path, "chosen.sv", "module chosen;\nendmodule\n")
    write(tmp_path, "other.sv", "module other;\nendmodule\n")
    for _ in range(2):
        rb, _ = build(tmp_path, [defs], save=save)
        assert rb is not None
        assert {p.name for p in rb.ordered_paths} == {"chosen.sv", "top.sv"}


@pytest.mark.parametrize("source", [
    "module top;\nimport dep::*;\nendmodule\n",
    "import dep::*;\nmodule top;\nendmodule\n",
    "module top;\nlogic x;\nimport dep::item;\nendmodule\n",
    "package outer;\nlocalparam int X=0;\nimport dep::*;\nendpackage\n",
])
def test_import_is_not_lost(source: str):
    result = scan_verilog_body(squeeze_for_dependency_scan(source))
    assert "dep" in result.referenced_modules


def test_package_transitive_closure(tmp_path: Path):
    write(tmp_path, "top.sv", "module top;\nimport outer::*;\nendmodule\n")
    write(tmp_path, "different.sv", "package outer;\nimport inner::*;\nendpackage\n")
    write(tmp_path, "inner.sv", "package inner;\nendpackage\n")
    rb, ctx = build(tmp_path)
    assert rb is not None and not ctx.exit_code
    assert [p.name for p in rb.ordered_paths] == ["inner.sv", "different.sv", "top.sv"]


@pytest.mark.parametrize("source", [None, "module top;\nmissing u();\nendmodule\n"])
def test_missing_definition_fails_without_output(tmp_path: Path, source: str | None):
    if source:
        write(tmp_path, "top.sv", source)
    rb, ctx = build(tmp_path)
    assert ctx.exit_code and rb is None
    assert not (tmp_path / "out.f").exists()


def test_missing_cli_returns_nonzero_and_preserves_output(tmp_path: Path):
    write(tmp_path, "top.sv", "module top;\nghost u();\nendmodule\n")
    out = write(tmp_path, "out.f", "previous successful output\n")
    root = Path(__file__).resolve().parents[1]
    cp = subprocess.run([sys.executable, str(root / "src"), "-s", str(tmp_path),
                         "-t", "top", "-o", str(out)], capture_output=True, text=True)
    assert cp.returncode != 0
    assert 'Not found module "ghost"' in cp.stderr
    assert "output:" not in cp.stderr
    assert out.read_text() == "previous successful output\n"


@pytest.mark.parametrize("form", ["direct", "nested", "library"])
def test_prelude_forms_preserve_macro_order(tmp_path: Path, form: str):
    defs = write(tmp_path, "defs.svh", '`include "switch.svh"\n`undef OFF\n')
    write(tmp_path, "switch.svh", "`define PICK\n")
    pre = write(tmp_path, "pre.f", "+define+OFF\n" +
                ("-v defs.svh\n" if form == "library" else "defs.svh\n") +
                "+define+AFTER\n")
    if form == "nested":
        pre = write(tmp_path, "root.f", "-f pre.f\n")
    write(tmp_path, "top.sv", "module top;\n`ifdef PICK\nchosen u();\n`else\nwrong u();\n`endif\n`ifdef OFF\nwrong2 u();\n`endif\nendmodule\n")
    write(tmp_path, "chosen.sv", "module chosen;\nendmodule\n")
    rb, ctx = build(tmp_path, [pre])
    assert rb is not None and not ctx.exit_code
    assert ctx.session_state.defines == {"PICK": "", "AFTER": ""}
    assert [p.name for p in rb.ordered_paths] == ["chosen.sv", "top.sv"]


def test_prelude_macro_changes_invalidate_warm_cache(tmp_path: Path):
    defs = write(tmp_path, "defs.svh", "`define PICK\n")
    write(tmp_path, "top.sv", "module top;\n`ifdef PICK\nchosen u();\n`else\nother u();\n`endif\nendmodule\n")
    for name in ["chosen", "other"]:
        write(tmp_path, name + ".sv", f"module {name};\nendmodule\n")
    rb, _ = build(tmp_path, [defs], save=True)
    assert {p.name for p in rb.ordered_paths} == {"chosen.sv", "top.sv"}
    defs.write_text("`undef PICK\n", encoding="utf-8")
    rb, _ = build(tmp_path, [defs], save=True)
    assert {p.name for p in rb.ordered_paths} == {"other.sv", "top.sv"}


@pytest.mark.parametrize("source", [
    "module top;\ninitial begin\nimport dep::*;\nend\nendmodule\n",
    "module top #(parameter W=1) (input dep::t p);\nimport dep::*;\nendmodule\n",
    "package automatic top;\nimport dep::item;\nendpackage\n",
    "package static top; import dep::*; endpackage\n",
])
def test_import_survives_destructive_squeeze(source: str):
    result = scan_verilog_body(squeeze_for_dependency_scan(source))
    assert "dep" in result.referenced_modules


def test_import_noise_and_inactive_branch_do_not_create_dependencies(tmp_path: Path):
    write(tmp_path, "top.sv", '''// import comment_pkg::*;
module top;
  string x = "import string_pkg::*;";
  import "DPI-C" function void ping();
`ifdef DISABLED
  import inactive_pkg::*;
`endif
endmodule
''')
    rb, ctx = build(tmp_path)
    assert rb is not None and not ctx.exit_code
    assert ctx.session_state.file_refs[tmp_path / "top.sv"] == []


@pytest.mark.parametrize("source", ["module other;\nendmodule\n",
    "`ifdef OFF\nmodule top;\nendmodule\n`endif\n"])
def test_filename_is_not_proof_of_definition(tmp_path: Path, source: str):
    write(tmp_path, "top.sv", source)
    rb, ctx = build(tmp_path)
    assert rb is None and ctx.exit_code == 1
    assert "top" not in ctx.session_state.module_to_file
    assert not (tmp_path / "out.f").exists()


def test_missing_package_is_fatal(tmp_path: Path):
    write(tmp_path, "top.sv", "import lost::*;\nmodule top;\nendmodule\n")
    rb, ctx = build(tmp_path)
    assert rb is None and ctx.exit_code == 1
    assert ctx.session_state.unresolved_modules == ["lost"]


def test_prelude_missing_include_is_fatal(tmp_path: Path):
    defs = write(tmp_path, "defs.svh", '`include "lost.svh"\n')
    write(tmp_path, "top.sv", "module top;\nendmodule\n")
    rb, ctx = build(tmp_path, [defs])
    assert rb is None and ctx.exit_code == 1
    assert not (tmp_path / "out.f").exists()


def test_package_lifetime_rg_fallback(tmp_path: Path):
    write(tmp_path, "top.sv", "import dep::*;\nmodule top;\nendmodule\n")
    write(tmp_path, "other_name.sv", "package automatic dep;\nendpackage\n")
    rb, ctx = build(tmp_path)
    assert rb is not None and not ctx.exit_code
    assert [p.name for p in rb.ordered_paths] == ["other_name.sv", "top.sv"]


def test_prelude_dependencies_are_inserted_before_importer(tmp_path: Path):
    pre = write(tmp_path, "outer.sv", "package outer;\nimport inner::*;\nendpackage\n")
    write(tmp_path, "inner.sv", "package inner;\nendpackage\n")
    write(tmp_path, "top.sv", "import outer::*;\nmodule top;\nendmodule\n")
    rb, ctx = build(tmp_path, [pre])
    assert rb is not None and not ctx.exit_code
    assert (tmp_path / "out.f").read_text().splitlines() == ["inner.sv", "outer.sv", "top.sv"]


def test_conflicting_fixed_prelude_order_is_rejected(tmp_path: Path):
    outer = write(tmp_path, "outer.sv", "package outer;\nimport inner::*;\nendpackage\n")
    inner = write(tmp_path, "inner.sv", "package inner;\nendpackage\n")
    write(tmp_path, "top.sv", "module top;\nendmodule\n")
    rb, ctx = build(tmp_path, [outer, inner])
    assert rb is None and ctx.exit_code == 1
    assert not (tmp_path / "out.f").exists()


def test_prelude_directives_ignore_comments_and_support_function_macro(tmp_path: Path):
    pre = write(tmp_path, "defs.svh", '''/*
`define BAD
*/
`define FUNC(x) x
`ifdef FUNC // selected
`define GOOD
`endif
''')
    write(tmp_path, "top.sv", "module top;\n`ifdef BAD\nghost u();\n`endif\n`ifndef GOOD\nghost2 u();\n`endif\nendmodule\n")
    rb, ctx = build(tmp_path, [pre])
    assert rb is not None and not ctx.exit_code
    assert ctx.session_state.defines == {"FUNC": "x", "GOOD": ""}


def test_import_cycle_is_rejected(tmp_path: Path):
    write(tmp_path, "top.sv", "import aa::*;\nmodule top;\nendmodule\n")
    write(tmp_path, "aa.sv", "package aa;\nimport bb::*;\nendpackage\n")
    write(tmp_path, "bb.sv", "package bb;\nimport aa::*;\nendpackage\n")
    rb, ctx = build(tmp_path)
    assert rb is None and ctx.exit_code == 1
    assert not (tmp_path / "out.f").exists()


def test_old_cache_cannot_hide_package_dependency(tmp_path: Path):
    import sqlite3
    from core.archive_sqlite import FileParseArchive

    top = write(tmp_path, "top.sv", "import dep::*;\nmodule top;\nendmodule\n")
    write(tmp_path, "dep.sv", "package dep;\nendpackage\n")
    db = tmp_path / "cache.db"
    archive = FileParseArchive(db)
    archive.put(top, ["top"], [], [])
    archive.upsert_module_hints(top, ["top"], [])
    archive.close()
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE archive_meta SET value='2' WHERE key='archive_schema'")
    rb, ctx = build(tmp_path, save=True)
    assert rb is not None and not ctx.exit_code
    assert [p.name for p in rb.ordered_paths] == ["dep.sv", "top.sv"]


def test_missing_dependency_with_warm_cache_preserves_output(tmp_path: Path):
    write(tmp_path, "top.sv", "module top;\nleaf u();\nendmodule\n")
    leaf = write(tmp_path, "leaf.sv", "module leaf;\nendmodule\n")
    rb, _ = build(tmp_path, save=True)
    assert rb is not None
    previous = (tmp_path / "out.f").read_bytes()
    leaf.unlink()
    rb, ctx = build(tmp_path, save=True)
    assert rb is None and ctx.exit_code == 1
    assert (tmp_path / "out.f").read_bytes() == previous


@pytest.mark.parametrize("source", [
    "module top; endmodule\n",
    "module top; child u(); endmodule\nmodule child; endmodule\n",
    "module static top; endmodule\n",
])
def test_strict_resolution_accepts_compact_valid_definitions(tmp_path: Path, source: str):
    write(tmp_path, "top.sv", source)
    rb, ctx = build(tmp_path)
    assert rb is not None and not ctx.exit_code


def test_include_import_change_invalidates_cache(tmp_path: Path):
    write(tmp_path, "top.sv", '`include "imports.svh"\nmodule top;\nendmodule\n')
    header = write(tmp_path, "imports.svh", "// no imports yet\n")
    write(tmp_path, "dep.sv", "package dep;\nendpackage\n")
    rb, _ = build(tmp_path, save=True)
    assert [p.name for p in rb.ordered_paths] == ["top.sv"]
    header.write_text("import dep::*;\n", encoding="utf-8")
    rb, ctx = build(tmp_path, save=True)
    assert rb is not None and not ctx.exit_code
    assert [p.name for p in rb.ordered_paths] == ["dep.sv", "top.sv"]
    header.unlink()
    rb, ctx = build(tmp_path, save=True)
    assert rb is None and ctx.exit_code == 1


def test_quoted_prelude_source_participates_in_macro_state(tmp_path: Path):
    write(tmp_path, "defs.svh", "`define PICK\n")
    pre = write(tmp_path, "pre.f", '"defs.svh"\n')
    write(tmp_path, "top.sv", "module top;\n`ifndef PICK\nghost u();\n`endif\nendmodule\n")
    rb, ctx = build(tmp_path, [pre])
    assert rb is not None and not ctx.exit_code
    assert "PICK" in ctx.session_state.defines


def test_missing_plain_prelude_source_cannot_be_silently_kept(tmp_path: Path):
    pre = write(tmp_path, "pre.f", "missing.sv\n")
    with pytest.raises(FileNotFoundError, match="missing.sv"):
        build(tmp_path, [pre])
    assert not (tmp_path / "out.f").exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junction regression")
def test_prelude_junction_alias_is_deduplicated(tmp_path: Path):
    real = tmp_path / "rtl"
    real.mkdir()
    alias = tmp_path / "alias"
    cp = subprocess.run(["cmd", "/c", "mklink", "/J", str(alias), str(real)],
                        capture_output=True, text=True)
    assert cp.returncode == 0, cp.stderr
    leaf = write(real, "leaf.sv", "module leaf;\nendmodule\n")
    write(real, "top.sv", "module top;\nleaf u();\nendmodule\n")
    rb, ctx = build(tmp_path, [alias / "leaf.sv", leaf])
    assert rb is not None and not ctx.exit_code
    lines = (tmp_path / "out.f").read_text().splitlines()
    assert len([line for line in lines if (tmp_path / line).resolve() == leaf.resolve()]) == 1
    assert "alias/leaf.sv" == lines[0]
