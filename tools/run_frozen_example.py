"""Run the full example and dependency regressions through a frozen program."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

from release_support import ROOT, sha


def verify(executable: Path) -> dict:
    executable = executable.resolve()
    env = {k: v for k, v in os.environ.items() if k not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}
    env.update(PATH="", PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    checked = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="frozen-filelist-") as temp:
        work = Path(temp)

        def run(args: list[str], expected: int = 0):
            cp = subprocess.run([str(executable), *args], cwd=work, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=45)
            assert cp.returncode == expected, (args, cp.returncode, cp.stdout, cp.stderr)
            return cp

        example = work / "example"
        shutil.copytree(ROOT / "example/complex_rtl", example / "complex_rtl")
        shutil.copyfile(ROOT / "example/run_prelude.f", example / "run_prelude.f")
        output = work / "example.f"
        run(["-s", str(example / "complex_rtl"), "-t", "top_chip", "-p", str(example / "run_prelude.f"),
             "-o", str(output), "--path-style", "absolute", "--debug-dump", str(work / "debug"),
             "--log", str(work / "run.log")])
        files = [Path(line) for line in output.read_text(encoding="utf-8").splitlines()
                 if line and not line.startswith(("+", "-"))]
        actual = sorted(p.resolve().relative_to((example / "complex_rtl").resolve()).as_posix() for p in files)
        expected_files = json.loads((ROOT / "tests/data/complex_expected.json").read_text(encoding="utf-8"))
        assert actual == expected_files and len(set(files)) == len(files)
        assert files[-1].name == "top_chip.v" and all(p.is_file() for p in files)
        assert (work / "debug/module_ref_index.txt").is_file()
        assert (work / "run.log").stat().st_size > 0
        checked.append("full_complex_example_exact_20_files_and_debug")

        rtl = work / "unicode-源码"
        rtl.mkdir()
        texts = {
            "defs.svh": '`include "switch.svh"\n',
            "switch.svh": "`define PICK\n",
            "base.sv": "package base; typedef logic item_t; endpackage\n",
            "dep.sv": "package dep; import base::*; endpackage\n",
            "leaf.sv": "module leaf; endmodule\n",
            "other.sv": "module other; endmodule\n",
            "top.sv": "import dep::*;\nmodule top;\n`ifdef PICK\nleaf u();\n`else\nother u();\n`endif\nendmodule\n",
            "inner.f": '"defs.svh"\nleaf.sv\n',
            "pre.f": "-f inner.f\n",
        }
        for name, text in texts.items():
            (rtl / name).write_text(text, encoding="utf-8")
        output = work / "out.f"
        args = ["-s", str(rtl), "-t", "top", "-p", str(rtl / "pre.f"), "-o", str(output), "--save", str(work / "parse.db")]
        for mode in ["cold", "warm"]:
            run(args)
            paths = [work / line for line in output.read_text(encoding="utf-8").splitlines() if line]
            assert len(paths) == len({p.resolve() for p in paths})
            names = [p.name for p in paths]
            assert sorted(names) == ["base.sv", "defs.svh", "dep.sv", "leaf.sv", "top.sv"]
            assert names.index("base.sv") < names.index("dep.sv") < names.index("top.sv")
            checked.append("ordered_prelude_macros_packages_" + mode)
        (rtl / "switch.svh").write_text("`undef PICK\n", encoding="utf-8")
        run(args)
        assert "other.sv" in output.read_text(encoding="utf-8")
        checked.append("prelude_include_changes_invalidate_selection")
        before = output.read_bytes()
        (rtl / "other.sv").unlink()
        cp = run(args, 1)
        assert 'Not found module "other"' in cp.stderr and "output:" not in cp.stderr
        assert output.read_bytes() == before
        checked.append("warm_missing_module_preserves_output")
        missing = work / "missing.f"
        cp = run(["-s", str(rtl), "-t", "absent", "-o", str(missing)], 1)
        assert not missing.exists() and 'Not found module "absent"' in cp.stderr
        checked.append("missing_top_no_output")
        (rtl / "dep.sv").unlink()
        cp = run(args, 1)
        assert 'Not found module "dep"' in cp.stderr
        checked.append("missing_package_is_error")
        (rtl / "switch.svh").unlink()
        cp = run(args, 1)
        assert "Not found include" in cp.stderr
        checked.append("missing_prelude_include_is_error")
        auto = work / "automatic"
        (auto / "rtl").mkdir(parents=True)
        (auto / "headers").mkdir()
        (auto / "rtl/auto_top.sv").write_text('`include "auto.svh"\nmodule auto_top;\nendmodule\n', encoding="utf-8")
        (auto / "headers/auto.svh").write_text("// auto include\n", encoding="utf-8")
        auto_output = work / "auto.f"
        auto_args = ["-s", str(auto), "-t", "auto_top", "-o", str(auto_output), "--save", str(work / "auto.db")]
        for mode in [[], [], ["--path-style", "absolute"]]:
            run(auto_args + mode)
            incs = [line.removeprefix("+incdir+").strip('"') for line in auto_output.read_text(encoding="utf-8").splitlines()
                    if line.startswith("+incdir+")]
            assert len(incs) == 1 and (work / incs[0] / "auto.svh").is_file()
        checked.append("auto_incdir_cold_warm_and_new_output_style")
        shadow = auto / "shadow"
        shadow.mkdir()
        (shadow / "auto_top.sv").write_text("module auto_top; endmodule\n", encoding="utf-8")
        duplicate_args = ["-s", str(auto), "-t", "auto_top", "-o", str(auto_output)]
        run(duplicate_args, 1)
        run(duplicate_args + ["--exclude", str(shadow)])
        assert "shadow" not in auto_output.read_text(encoding="utf-8")
        checked.append("duplicate_definition_and_exclusion")
        combined = work / "resolution"
        sources, library = combined / "rtl", combined / "lib"
        sources.mkdir(parents=True)
        library.mkdir()
        (sources / "netlist.sv").write_text(
            "module helper;\ninitial begin\n" + "  ;\n" * 600000 +
            "end endmodule\nmodule resolution_top;\n"
            "import resolution_pkg::*;\ninitial $display(\"%d\", C::W);\n"
            "localparam int W = resolution_pkg::WIDTH;\n"
            "lib_a #(.W(resolution_pkg::WIDTH)) u();\nendmodule\n", encoding="utf-8")
        package = sources / "package_source.sv"
        package_text = "package resolution_pkg; parameter WIDTH=1; class C; parameter W=1; endclass endpackage\n"
        package.write_text(package_text, encoding="utf-8")
        (library / "lib_a.model").write_text("module lib_a #(parameter W=1);\nlib_b u();\nendmodule\n", encoding="utf-8")
        lib_b = library / "lib_b.model"
        lib_b.write_text("module lib_b; endmodule\n", encoding="utf-8")
        prelude = combined / "pre.f"
        prelude.write_text("-y lib\n+libext+.model\n", encoding="utf-8")
        combined_output = combined / "out.f"
        combined_args = ["-s", str(sources), "-t", "resolution_top", "-p", str(prelude),
                         "-o", str(combined_output), "--save", str(combined / "cache.db")]
        for mode in ["cold", "warm"]:
            run(combined_args)
            lines = combined_output.read_text(encoding="utf-8").splitlines()
            assert lines.index("lib/lib_b.model") < lines.index("lib/lib_a.model") < lines.index("rtl/netlist.sv")
            assert lines.index("rtl/package_source.sv") < lines.index("rtl/netlist.sv")
            assert lines.count("rtl/netlist.sv") == 1
        checked.append("large_compact_definition_scoped_package_library_cold_warm")
        preserved = combined_output.read_bytes()
        package.unlink()
        assert 'Not found module "resolution_pkg"' in run(combined_args, 1).stderr
        assert combined_output.read_bytes() == preserved
        checked.append("missing_scoped_package_preserves_output")
        package.write_text(package_text, encoding="utf-8")
        lib_b.unlink()
        assert 'Not found module "lib_b"' in run(combined_args, 1).stderr
        assert combined_output.read_bytes() == preserved
        checked.append("missing_transitive_library_preserves_output")
    return {"executable": executable.name, "sha256": sha(executable), "features": checked,
            "seconds": round(time.monotonic() - started, 3), "independent_cwd": True,
            "empty_path": True, "source_imports_disabled": True}


if __name__ == "__main__":
    print(json.dumps(verify(Path(sys.argv[1])), indent=2))
