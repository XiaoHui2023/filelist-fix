"""Cross-check generated filelists and deliberate mutations with optional pyslang.

Install pyslang separately, or pass --pyslang-path for an isolated installation.
Run with the project's Python interpreter; this does not add a runtime dependency.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def compile_filelist(path: Path, pyslang_path: Path | None) -> int:
    if pyslang_path:
        sys.path.insert(0, str(pyslang_path))
    from pyslang.driver import Driver

    os.chdir(path.parent)
    driver = Driver()
    driver.addStandardArgs()
    if not driver.parseCommandLine(f'slang --single-unit -f "{path.name}"'):
        return 2
    if not driver.processOptions() or not driver.parseAllSources():
        return 2
    return 0 if driver.runFullCompilation(quiet=True) else 1


def verify(pyslang_path: Path | None) -> dict:
    def compiler(path: Path) -> subprocess.CompletedProcess:
        args = [sys.executable, str(Path(__file__).resolve()), "--compile", str(path)]
        if pyslang_path:
            args += ["--pyslang-path", str(pyslang_path)]
        return subprocess.run(args, capture_output=True, text=True, timeout=30)

    results = []
    with tempfile.TemporaryDirectory(prefix="closure-slang-") as temp:
        work = Path(temp)
        sources = {
            "defs.svh": '`include "switch.svh"\n',
            "switch.svh": "`define PICK\n",
            "base.sv": "package base;\ntypedef logic item_t;\nendpackage\n",
            "dep.sv": "package dep;\nimport base::*;\ntypedef item_t exported_t;\nendpackage\n",
            "chosen.sv": "module chosen;\nendmodule\n",
            "wrong.sv": "module wrong;\nendmodule\n",
            "top.sv": "import dep::*;\nmodule top;\nexported_t value;\n`ifdef PICK\nchosen u();\n`else\nwrong u();\n`endif\nendmodule\n",
            "nested.f": "defs.svh\n",
            "pre.f": "-f nested.f\ndep.sv\n",
        }
        for name, source in sources.items():
            (work / name).write_text(source, encoding="utf-8")
        out = work / "out.f"
        for mode in ["cold", "warm"]:
            cp = subprocess.run([
                sys.executable, str(ROOT / "src"), "-s", str(work), "-t", "top",
                "-p", str(work / "pre.f"), "-o", str(out), "--save", str(work / "cache.db"),
            ], capture_output=True, text=True, timeout=30)
            assert cp.returncode == 0, cp.stderr
            lines = out.read_text(encoding="utf-8").splitlines()
            assert [Path(line).name for line in lines] == [
                "defs.svh", "base.sv", "dep.sv", "chosen.sv", "top.sv",
            ], lines
            assert all((work / line).is_file() for line in lines)
            assert len({(work / line).resolve() for line in lines}) == len(lines)
            checked = compiler(out)
            assert checked.returncode == 0, checked.stdout + checked.stderr
            results.append({"case": mode, "passed": True, "filelist": lines,
                            "compiler_stdout": checked.stdout, "compiler_stderr": checked.stderr})

        def omit(name: str) -> str:
            return "\n".join(line for line in lines if Path(line).name != name) + "\n"

        (work / "duplicate.sv").write_text(sources["chosen.sv"], encoding="utf-8")
        mutations = {
            "missing_package": omit("base.sv"),
            "missing_module": omit("chosen.sv"),
            "missing_prelude": omit("defs.svh"),
            "duplicate_definition": "\n".join([*lines, "duplicate.sv"]) + "\n",
        }
        for name, text in mutations.items():
            # Without the prelude, the real selected module is wrong; omit it as well.
            if name == "missing_prelude":
                assert "wrong.sv" not in text
            mutant = work / (name + ".f")
            mutant.write_text(text, encoding="utf-8")
            checked = compiler(mutant)
            assert checked.returncode == 1, (name, checked.stdout, checked.stderr)
            results.append({"case": name, "passed": True, "expected_rejection": True,
                            "compiler_stdout": checked.stdout, "compiler_stderr": checked.stderr})

    return {"oracle": "pyslang", "checks": results, "passed": len(results)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyslang-path", type=Path)
    parser.add_argument("--compile", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if args.compile:
        return compile_filelist(args.compile.resolve(), args.pyslang_path)
    report = verify(args.pyslang_path)
    text = json.dumps(report, indent=2)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
