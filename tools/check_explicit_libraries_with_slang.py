"""Compile generated -v lists independently, including semantic and missing-input controls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def inspect(path: Path, oracle: Path) -> dict:
    sys.path.insert(0, str(oracle))
    from pyslang.driver import Driver
    os.chdir(path.parent)
    driver = Driver()
    driver.addStandardArgs()
    assert driver.parseCommandLine(f'slang --single-unit -f "{path.name}"')
    assert driver.processOptions() and driver.parseAllSources()
    compilation = driver.createCompilation()
    root = compilation.getRoot()
    errors = sum(d.isError() for d in compilation.getAllDiagnostics())
    values = {}
    for instance in root.topInstances:
        if instance.name == 'top':
            child = instance.body.find('u')
            if child is not None and hasattr(child, 'body'):
                parameter = child.body.find('VALUE')
                if parameter is not None:
                    values['u.VALUE'] = str(parameter.value)
    return {'errors': errors, 'values': values}


def verify(oracle: Path) -> dict:
    checks = []
    env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}
    with tempfile.TemporaryDirectory(prefix='explicit-library-slang-') as temp:
        work = Path(temp)
        out = work / 'out.f'
        pre = work / 'pre.f'
        udp = 'primitive shared_udp(q,a);\noutput q; input a;\ntable\n0 : 0;\n1 : 1;\nendtable\nendprimitive\n'

        def compile_list(path):
            cp = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--inspect', str(path),
                                 '--pyslang-path', str(oracle)], capture_output=True, text=True,
                                encoding='utf-8', env=env, timeout=20, check=True)
            return json.loads(cp.stdout)

        for kind in ['udp', 'module']:
            for name, value in [('a', 8), ('b', 16)]:
                duplicate = udp if kind == 'udp' else f'module shared_udp; localparam int VALUE={value}; endmodule\n'
                (work / (name + '.v')).write_text(duplicate + f'module only_{name}; endmodule\n')
            call = 'wire q,a; shared_udp u(q,a);' if kind == 'udp' else 'shared_udp u();'
            (work / 'top.sv').write_text(f'module top; {call} only_a x(); only_b y(); endmodule\n')
            for reverse in [False, True]:
                names = ['b.v', 'a.v'] if reverse else ['a.v', 'b.v']
                pre.write_text(''.join('-v ' + name + '\n' for name in names))
                reference = work / 'reference.f'
                reference.write_text(pre.read_text() + 'top.sv\n')
                expected = compile_list(reference)
                assert expected['errors'] == 0, expected
                (work / 'cache.db').unlink(missing_ok=True)
                for mode in ['cold', 'warm']:
                    subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'top',
                                    '-p', str(pre), '-o', str(out), '--save', str(work / 'cache.db')],
                                   capture_output=True, env=env, timeout=20, check=True)
                    lines = out.read_text().splitlines()
                    assert lines == ['-v ' + name for name in names] + ['top.sv'], lines
                    result = compile_list(out)
                    assert result['errors'] == 0, result
                    if kind == 'module':
                        assert result['values'] == expected['values'], (result, expected)
                        assert result['values']['u.VALUE'] in {'8', '16'}, result
                    checks.append({'kind': kind, 'reverse': reverse, 'mode': mode, 'compiler': result})
                # Each file has a required unique export: dropping either must fail.
                for missing in names:
                    mutant = work / 'missing.f'
                    mutant.write_text('\n'.join(line for line in lines if line != '-v ' + missing) + '\n')
                    result = compile_list(mutant)
                    assert result['errors'] > 0, result
                    checks.append({'kind': kind, 'reverse': reverse, 'removed': missing, 'rejected': True})
        # Calibrate the semantic oracle: reversing the library order changes VALUE.
        wrong = work / 'reversed.f'
        wrong.write_text('-v a.v\n-v b.v\ntop.sv\n')
        result = compile_list(wrong)
        assert result['errors'] == 0 and result['values'] != expected['values'], result
        checks.append({'kind': 'wrong-library-order-value-mutant', 'detected': True})
    return {'checks': checks, 'source_sha': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pyslang-path', type=Path, required=True)
    parser.add_argument('--inspect', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.inspect:
        print(json.dumps(inspect(args.inspect, args.pyslang_path)))
    else:
        if args.report is None:
            parser.error('--report is required without --inspect')
        report = verify(args.pyslang_path)
        args.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps({'checks': len(report['checks'])}))
