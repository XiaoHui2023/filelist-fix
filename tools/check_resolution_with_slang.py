"""Optional independent compiler checks for resolution regressions (no runtime dependency)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def verify(oracle: Path) -> dict:
    checks = []
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='resolution-oracle-') as temp:
        work = Path(temp)
        rtl, lib = work / 'rtl', work / 'lib'
        rtl.mkdir()
        lib.mkdir()
        inputs = {
            rtl / 'netlist.sv': 'module helper;\ninitial begin\n' + '  ;\n' * 600000 +
                'end endmodule\nmodule top(input dep::item_t x);\n'
                'import dep::*;\ninitial $display("%d", C::W);\n'
                'C same_name_instance(.x(C::W));\n'
                'localparam int W=dep::WIDTH;\ncell_a #(.W(dep::WIDTH)) u();\n'
                'initial $display("%d", dep::C::W);\nendmodule\n',
            rtl / 'package_source.sv': 'package dep; typedef int item_t; parameter WIDTH=1; '
                'class C; parameter W=1; endclass endpackage\n',
            rtl / 'C.sv': 'module C(input int x); endmodule\n',
            lib / 'cell_a.model': 'module cell_a #(parameter W=1);\ncell_b u();\nendmodule\n',
            lib / 'cell_b.model': 'module cell_b; endmodule\n',
            work / 'pre.f': '-y lib\n+libext+.model\n',
        }
        for path, text in inputs.items():
            path.write_text(text, encoding='utf-8')
        for mode in ['cold', 'warm']:
            args = [sys.executable, str(ROOT / 'src'), '-s', str(rtl), '-t', 'top',
                    '-p', str(work / 'pre.f'), '-o', str(work / 'out.f'), '--save', str(work / 'cache.db')]
            cp = subprocess.run(args, capture_output=True, text=True, timeout=60)
            assert cp.returncode == 0, cp.stderr
            lines = (work / 'out.f').read_text().splitlines()
            assert sum('package_source.sv' in line for line in lines) == 1
            assert sum('netlist.sv' in line for line in lines) == 1
            assert lines.index('lib/cell_b.model') < lines.index('lib/cell_a.model') < lines.index('rtl/netlist.sv')
            # Remove library search directives: only the explicit generated closure
            # is compiled, so compiler auto-discovery cannot hide a missing edge.
            explicit = work / 'explicit.f'
            explicit.write_text('\n'.join(line for line in lines if not line.startswith(('-y ', '+libext+'))) + '\n')
            compile_args = [sys.executable, str(ROOT / 'tools/check_closure_with_slang.py'),
                            '--compile', str(explicit), '--pyslang-path', str(oracle)]
            compiled = subprocess.run(compile_args, capture_output=True, text=True, timeout=60)
            assert compiled.returncode == 0, compiled.stdout + compiled.stderr
            checks.append({'case': mode, 'explicit_closure_compiled': True, 'filelist': lines,
                           'input_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}})
        for omitted in ['package_source.sv', 'cell_b.model']:
            explicit.write_text('\n'.join(line for line in lines if not line.startswith(('-y ', '+libext+'))
                                          and omitted not in line) + '\n')
            cp = subprocess.run(compile_args, capture_output=True, text=True, timeout=60)
            assert cp.returncode == 1, cp.stdout + cp.stderr
            checks.append({'case': 'omit_' + omitted, 'expected_rejection': True,
                           'diagnostics': cp.stdout + cp.stderr})
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    return {'oracle': 'pyslang', 'source_sha': revision, 'checks': checks, 'seconds': round(time.monotonic() - started, 3)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pyslang-path', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.pyslang_path)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'passed': len(result['checks']), 'seconds': result['seconds']}))
