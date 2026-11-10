"""Compare compact lists with independent handwritten library configurations."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def verify(oracle: Path) -> dict:
    checks = []
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    with tempfile.TemporaryDirectory(prefix='directory-library-slang-') as temp:
        work = Path(temp); lib = work / 'models space'; lib.mkdir()
        (work / 'top.sv').write_text('module top; cell0 u(); cell1 v(); endmodule\n')
        def compile_list(path):
            cp = subprocess.run([sys.executable, str(ROOT / 'tools/check_explicit_libraries_with_slang.py'),
                                 '--inspect', str(path), '--pyslang-path', str(oracle)],
                                cwd=work, env=env, capture_output=True, text=True, encoding='utf-8',
                                timeout=20, check=True)
            return json.loads(cp.stdout)
        for kind in ['explicit', 'cell-marker', 'custom-extension', 'bundle']:
            for path in lib.iterdir():
                path.unlink()
            ext = '.model' if kind == 'custom-extension' else '.v'
            for i in range(2):
                body = f'module cell{i}; localparam int VALUE={8+i}; endmodule\n'
                if kind == 'cell-marker':
                    body = '`celldefine\n' + body + '`endcelldefine\n'
                (lib / (f'cell{i}' + ext)).write_text(body)
            paths = [lib / ('cell0' + ext), lib / ('cell1' + ext)]
            if kind == 'bundle':
                (lib / 'bundle.v').write_text(''.join(path.read_text() for path in paths))
                for path in paths:
                    path.unlink()
                paths = [lib / 'bundle.v']
            reference = work / 'reference.f'
            reference.write_text(''.join('-v "models space/' + path.name + '"\n' for path in paths) + 'top.sv\n')
            expected = compile_list(reference)
            assert expected == {'errors': 0, 'values': {'u.VALUE': '8'}}, expected
            pre = work / 'pre.f'
            if kind == 'cell-marker':
                pre.write_text('')
            elif kind == 'custom-extension':
                pre.write_text('+libext+ .model\n-y "models space"\n')
            else:
                pre.write_text(reference.read_text().replace('top.sv\n', ''))
            (work / 'cache.db').unlink(missing_ok=True)
            for mode in ['cold', 'warm']:
                out = work / 'out.f'
                cp = subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'top',
                                     '-p', str(pre), '-o', str(out), '--save', str(work / 'cache.db'),
                                     '--compact-libs'], env=env, capture_output=True, timeout=20)
                assert cp.returncode == 0, cp.stderr
                result = compile_list(out)
                assert result == expected, (result, expected, out.read_text())
                assert ('-y "models space"' in out.read_text()) == (kind != 'bundle')
                checks.append({'kind': kind, 'mode': mode, 'compiler': result, 'lines': out.read_text().splitlines()})
            missing = work / 'missing.f'
            missing.write_text('top.sv\n')
            assert compile_list(missing)['errors'] > 0
            checks.append({'kind': kind, 'removed_library_rejected': True})
        wrong = work / 'wrong-directory.f'
        wrong.write_text('+libext+.v\n-y "models space"\ntop.sv\n')
        assert compile_list(wrong)['errors'] > 0
        checks.append({'kind': 'bundle-forced-to-directory-mutant', 'rejected': True})
    return {'checks': checks, 'source_sha': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pyslang-path', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    result = verify(args.pyslang_path)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'checks': len(result['checks'])}))
