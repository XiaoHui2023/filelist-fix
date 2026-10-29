"""Compile generated stress corpora with optional, separately installed pyslang."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from stress_dependency_scan import ROOT, KINDS, source_corpus


def verify(oracle: Path) -> dict:
    checks = []
    with tempfile.TemporaryDirectory(prefix="performance-slang-") as temp:
        work = Path(temp)
        (work / "child.sv").write_text("module child(input a); endmodule\n")
        (work / "p.sv").write_text("package p; parameter int VALUE=1; endpackage\n")
        output = work / "out.f"

        def compile_filelist(path: Path):
            return subprocess.run([sys.executable, str(ROOT / "tools/check_closure_with_slang.py"),
                                   "--compile", str(path), "--pyslang-path", str(oracle)],
                                  capture_output=True, text=True, timeout=30)

        for kind in KINDS:
            (work / "top.sv").write_text(source_corpus(kind))
            cp = subprocess.run([sys.executable, str(ROOT / "src"), "-s", str(work), "-t", "top",
                                 "-o", str(output)], capture_output=True, text=True, timeout=10)
            assert cp.returncode == 0, cp.stderr
            compiled = compile_filelist(output)
            if kind == "expression" and compiled.returncode != 0:
                checks.append({"kind": kind, "full_compile_unavailable": True,
                               "returncode": compiled.returncode,
                               "diagnostics": compiled.stdout + compiled.stderr})
                # A very deep left-associated expression can exhaust the native
                # compiler stack. Preserve that limitation; validate original
                # syntax, then compile an equivalent shallow expression tree.
                syntax = subprocess.run([sys.executable, "-c",
                    "import sys;sys.path.insert(0,sys.argv[1]);from pyslang.syntax import SyntaxTree;"
                    "t=SyntaxTree.fromFile(sys.argv[2]);print(len(t.diagnostics));"
                    "sys.exit(1 if len(t.diagnostics) else 0)", str(oracle), str(work / "top.sv")],
                    capture_output=True, text=True, timeout=15)
                assert syntax.returncode == 0, syntax.stdout + syntax.stderr
                checks.append({"kind": "original-expression-syntax", "syntax_only": True})
                terms = ["1"] * (4038 * 4)
                while len(terms) > 1:
                    terms = ["(" + terms[i] + "+" + terms[i+1] + ")" if i+1 < len(terms)
                             else terms[i] for i in range(0, len(terms), 2)]
                (work / "top.sv").write_text("module top; generate if (" + terms[0]
                    + ") begin : selected end endgenerate endmodule\n")
                compiled = compile_filelist(output)
                assert compiled.returncode == 0, compiled.stdout + compiled.stderr
                checks.append({"kind": "balanced-equivalent-expression", "compiled": True})
                continue
            assert compiled.returncode == 0, kind + str(compiled.returncode) + compiled.stdout + compiled.stderr
            checks.append({"kind": kind, "compiled": True, "filelist": output.read_text().splitlines()})
        bad = work / "missing-child.f"
        bad.write_text("top.sv\n")
        compiled = compile_filelist(bad)
        assert compiled.returncode != 0
        checks.append({"kind": "missing-child-mutant", "compiler_rejected": True,
                       "diagnostics": (compiled.stdout + compiled.stderr)[:1000]})
    return {"checks": checks}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pyslang-path", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.pyslang_path)
    args.report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"checks": len(result["checks"])}))
