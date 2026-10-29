"""Independent macro-order and scoped-call checks; pyslang stays optional."""
from __future__ import annotations
import argparse
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
    with tempfile.TemporaryDirectory(prefix='macro-call-oracle-') as temp:
        work = Path(temp)
        parent = work / 'top.sv'
        parent.write_text('`define WIDTH 8\nclass C; static function void g(); endfunction endclass\n'
            'module top; initial begin p::f(); C::g(); end\nchild u();\nendmodule\n')
        (work / 'p.sv').write_text('package p; function void f(); endfunction endpackage\n')
        (work / 'child.sv').write_text('module child;\nwire [`WIDTH-1:0] value;\n'
            '`ifdef WIDTH\nleaf u();\n`endif\nendmodule\n')
        (work / 'leaf.sv').write_text('module leaf; endmodule\n')
        out = work / 'out.f'
        def compile_filelist(path):
            return subprocess.run([sys.executable, str(ROOT / 'tools/check_closure_with_slang.py'),
                '--compile', str(path), '--pyslang-path', str(oracle)], capture_output=True,
                text=True, encoding='utf-8', timeout=30)
        for prelude in [False, True]:
            args = [sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'top',
                    '-o', str(out), '--save', str(work / ('pre.db' if prelude else 'normal.db'))]
            if prelude:
                args += ['-p', str(parent)]
            for mode in ['cold', 'warm']:
                cp = subprocess.run(args, capture_output=True, text=True, timeout=30)
                assert cp.returncode == 0, cp.stderr
                lines = out.read_text().splitlines()
                assert lines.index('top.sv') < lines.index('child.sv')
                assert set(lines) == {'p.sv', 'top.sv', 'leaf.sv', 'child.sv'}
                compiled = compile_filelist(out)
                assert compiled.returncode == 0, compiled.stdout + compiled.stderr
                checks.append({'case': ('prelude_' if prelude else 'normal_') + mode,
                               'compiled': True, 'filelist': lines})
        for name, bad in {
            'child_before_macro_provider': ['child.sv', *[p for p in lines if p != 'child.sv']],
            'missing_package': [p for p in lines if p != 'p.sv'],
        }.items():
            mutant = work / (name + '.f')
            mutant.write_text('\n'.join(bad) + '\n')
            compiled = compile_filelist(mutant)
            assert compiled.returncode == 1, compiled.stdout + compiled.stderr
            checks.append({'case': name, 'expected_rejection': True,
                           'diagnostics': compiled.stdout + compiled.stderr})
        parent.write_text('`define WIDTH 8\nmodule top;\nimport p::*;\nendmodule\n')
        (work / 'p.sv').write_text('package p;\nlocalparam int W=`WIDTH;\nendpackage\n')
        before = out.read_bytes()
        cp = subprocess.run(args, capture_output=True, text=True, timeout=30)
        assert cp.returncode != 0 and 'WIDTH' in cp.stderr
        assert out.read_bytes() == before
        checks.append({'case': 'hard_macro_package_cycle', 'expected_cli_rejection': True,
                       'diagnostics': cp.stderr})
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    return {'source_sha': revision, 'checks': checks, 'seconds': round(time.monotonic()-started, 3)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pyslang-path', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.pyslang_path)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'checks': len(result['checks']), 'seconds': result['seconds']}))
