"""Independently compile ordered macro corpora and inspect elaborated parameter values."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def inspect_filelist(path: Path, oracle: Path) -> int:
    sys.path.insert(0, str(oracle))
    from pyslang.driver import Driver
    os.chdir(path.parent)
    driver = Driver()
    driver.addStandardArgs()
    if not driver.parseCommandLine(f'slang --single-unit -f "{path.name}"') or not driver.processOptions() or not driver.parseAllSources():
        return 2
    compilation = driver.createCompilation()
    root = compilation.getRoot()
    errors = sum(d.isError() for d in compilation.getAllDiagnostics())
    values = {i.name: str(i.body.find('VALUE').value) for i in root.topInstances
              if i.name == 'probe' and i.body.find('VALUE') is not None}
    print(json.dumps({'errors': errors, 'values': values}))
    return 1 if errors else 0


def verify(oracle: Path) -> dict:
    checks = []
    def compile_filelist(path):
        cp = subprocess.run([sys.executable, str(Path(__file__).resolve()), '--inspect', str(path),
                             '--pyslang-path', str(oracle)], capture_output=True, text=True, timeout=20)
        assert cp.returncode in {0, 1}, cp.stdout + cp.stderr
        return cp.returncode, json.loads(cp.stdout)

    with tempfile.TemporaryDirectory(prefix='macro-condition-slang-') as temp:
        work = Path(temp)
        out = work / 'out.f'
        (work / 'a_defs.sv').write_text('`define FLAG\nmodule defs; endmodule\n')
        for leaf in ['set_leaf', 'unset_leaf']:
            (work / (leaf + '.sv')).write_text('module ' + leaf + '; endmodule\n')
        for kind in ['ifdef', 'ifndef', 'elsif']:
            branches = {'ifdef': '`ifdef FLAG\nlocalparam int VALUE=16;\nset_leaf u();\n`else\nlocalparam int VALUE=8;\nunset_leaf u();\n`endif',
                        'ifndef': '`ifndef FLAG\nlocalparam int VALUE=8;\nunset_leaf u();\n`else\nlocalparam int VALUE=16;\nset_leaf u();\n`endif',
                        'elsif': '`ifdef NEVER\nmissing u();\n`elsif FLAG\nlocalparam int VALUE=16;\nset_leaf u();\n`else\nlocalparam int VALUE=8;\nunset_leaf u();\n`endif'}
            (work / 'z_probe.sv').write_text('module probe;\n' + branches[kind] + '\nendmodule\n')
            for pinned in [False, True]:
                for first_defined in [False, True]:
                    tops = ['defs', 'probe'] if first_defined else ['probe', 'defs']
                    args = [sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', *tops,
                            '-o', str(out), '--save', str(work / 'cache.db')]
                    if pinned:
                        pre = work / 'pre.f'
                        pre.write_text('\n'.join(['a_defs.sv','z_probe.sv'] if first_defined else ['z_probe.sv','a_defs.sv'])+'\n')
                        args += ['-p', str(pre)]
                    (work / 'cache.db').unlink(missing_ok=True)
                    for mode in ['cold', 'warm']:
                        cp = subprocess.run(args, capture_output=True, text=True, timeout=15)
                        assert cp.returncode == 0, cp.stderr
                        code, result = compile_filelist(out)
                        assert code == 0 and result['values']['probe'] == ('16' if first_defined else '8'), result
                        checks.append({'kind': kind, 'prelude': pinned, 'defined_first': first_defined,
                                       'mode': mode, 'compiler': result, 'filelist': out.read_text().splitlines()})
        for reset in ['undef FLAG', 'undefineall']:
            (work / 'first.sv').write_text('`define FLAG\nmodule first; endmodule\n')
            (work / 'kill.sv').write_text('`' + reset + '\nmodule kill; endmodule\n')
            (work / 'z_probe.sv').write_text('module probe;\n' + branches['ifndef'] + '\nendmodule\n')
            (work / 'cache.db').unlink(missing_ok=True)
            for mode in ['cold', 'warm']:
                cp = subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work),
                                     '-t', 'first', 'kill', 'probe', 'defs', '-o', str(out),
                                     '--save', str(work / 'cache.db')], capture_output=True, text=True, timeout=15)
                assert cp.returncode == 0, cp.stderr
                code, result = compile_filelist(out)
                assert code == 0 and result['values']['probe'] == '8', result
                checks.append({'kind': reset, 'mode': mode, 'compiler': result})
        (work / 'first.sv').write_text('`define WIDTH 8\nmodule first; endmodule\n')
        (work / 'z_probe.sv').write_text('module probe;\nlocalparam int VALUE=`WIDTH;\nendmodule\n')
        (work / 'a_later.sv').write_text('`define WIDTH 16\nmodule later; endmodule\n')
        cp = subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'first', 'probe', 'later',
                             '-o', str(out)], capture_output=True, text=True, timeout=15)
        assert cp.returncode == 0, cp.stderr
        code, result = compile_filelist(out)
        assert code == 0 and result['values']['probe'] == '8', result
        checks.append({'kind': 'read-between-redefinitions', 'compiler': result})
        mutant = work / 'wrong-order.f'
        mutant.write_text('first.sv\na_later.sv\nz_probe.sv\n')
        code, result = compile_filelist(mutant)
        assert code == 0 and result['values']['probe'] == '16', result
        checks.append({'kind': 'wrong-value-mutant', 'wrong_value_detected': result['values']['probe'] != '8'})
        (work / 'shared.svh').write_text('`define WIDTH 8\n')
        (work / 'z_probe.sv').write_text('`include "shared.svh"\nmodule probe;\nreplica u();\nlocalparam int VALUE=`WIDTH;\nendmodule\n')
        (work / 'a_replica.sv').write_text('`include "shared.svh"\nmodule replica; endmodule\n')
        cp = subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'probe',
                             '-o', str(out)], capture_output=True, text=True, timeout=15)
        assert cp.returncode == 0, cp.stderr
        assert out.read_text().splitlines() == ['z_probe.sv', 'a_replica.sv']
        code, result = compile_filelist(out)
        assert code == 0 and result['values']['probe'] == '8', result
        checks.append({'kind': 'repeated-header-writers-parent-first', 'compiler': result})
    return {'checks': checks, 'source_sha': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pyslang-path', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    parser.add_argument('--inspect', type=Path)
    args = parser.parse_args()
    if args.inspect:
        raise SystemExit(inspect_filelist(args.inspect, args.pyslang_path))
    if args.report is None:
        parser.error('--report is required without --inspect')
    result = verify(args.pyslang_path)
    args.report.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps({'checks': len(result['checks'])}))
