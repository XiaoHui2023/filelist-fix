from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_cli(work, *extra):
    return subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', 'top',
                           '-o', str(work / 'out.f'), *map(str, extra)],
                          capture_output=True, text=True, encoding='utf-8', timeout=30)


@pytest.mark.parametrize('prelude', [False, True])
def test_macro_provider_parent_precedes_child(tmp_path, prelude):
    parent = tmp_path / 'top.sv'
    parent.write_text('`define WIDTH 8\nmodule top;\nchild u();\nendmodule\n')
    (tmp_path / 'child.sv').write_text('module child;\nwire [`WIDTH-1:0] value;\nendmodule\n')
    output = tmp_path / 'out.f'
    output.write_text('previous good output\n')
    args = ['--save', tmp_path / 'cache.db']
    if prelude:
        args += ['-p', parent]
    for _ in range(2):
        cp = run_cli(tmp_path, *args)
        assert cp.returncode == 0, cp.stderr
        assert output.read_text().splitlines() == ['top.sv', 'child.sv']


def test_independent_macro_provider_precedes_user(tmp_path):
    (tmp_path / 'z_defs.sv').write_text('`define WIDTH 8\nmodule defs; endmodule\n')
    (tmp_path / 'a_top.sv').write_text('module top;\nwire [`WIDTH-1:0] value;\nendmodule\n')
    for _ in range(2):
        cp = run_cli(tmp_path, '-t', 'defs', 'top', '--save', tmp_path / 'cache.db')
        assert cp.returncode == 0, cp.stderr
        assert (tmp_path / 'out.f').read_text().splitlines() == ['z_defs.sv', 'a_top.sv']


@pytest.mark.parametrize('call', ['p::f();', 'p :: f ();', 'p::\n f();'])
def test_package_call_is_not_an_instance(tmp_path, call):
    (tmp_path / 'p.sv').write_text('package p; function void f(); endfunction endpackage\n')
    (tmp_path / 'top.sv').write_text('module top; initial begin\n' + call + '\nend endmodule\n')
    cp = run_cli(tmp_path)
    assert cp.returncode == 0, cp.stderr
    assert (tmp_path / 'out.f').read_text().splitlines() == ['p.sv', 'top.sv']


def test_compact_class_call_is_not_an_instance(tmp_path):
    (tmp_path / 'top.sv').write_text('class C; static function void f(); endfunction endclass\nmodule top; initial C::f(); endmodule\n')
    cp = run_cli(tmp_path)
    assert cp.returncode == 0, cp.stderr
    assert (tmp_path / 'out.f').read_text().splitlines() == ['top.sv']


@pytest.mark.parametrize('scope', ['p', 'C'])
def test_scoped_void_cast_call_is_not_an_instance(tmp_path, scope):
    if scope == 'p':
        (tmp_path / 'p.sv').write_text('package p; function int f(); return 1; endfunction endpackage\n')
        prefix = ''
    else:
        prefix = 'class C; static function int f(); return 1; endfunction endclass\n'
    (tmp_path / 'top.sv').write_text('module top;\n' + prefix + "initial void'(" + scope + '::f());\nendmodule\n')
    cp = run_cli(tmp_path)
    assert cp.returncode == 0, cp.stderr
    if scope == 'p':
        assert 'p.sv' in (tmp_path / 'out.f').read_text()


@pytest.mark.parametrize('local', [
    '`define WIDTH 4\nwire [`WIDTH-1:0] value;',
    '`undef WIDTH\n`define WIDTH 4\nwire [`WIDTH-1:0] value;',
    '// `WIDTH\ninitial $display("`WIDTH");',
    '`ifdef NEVER\nwire [`WIDTH-1:0] value;\n`endif',
])
def test_local_or_inactive_macro_read_does_not_make_false_cycle(tmp_path, local):
    parent = tmp_path / 'top.sv'
    parent.write_text('`define WIDTH 8\nmodule top;\nchild u();\nendmodule\n')
    (tmp_path / 'child.sv').write_text('module child;\n' + local + '\nendmodule\n')
    cp = run_cli(tmp_path, '-p', parent)
    assert cp.returncode == 0, cp.stderr


@pytest.mark.parametrize('late', [False, True])
def test_command_define_position_is_respected(tmp_path, late):
    (tmp_path / 'top.sv').write_text('module top;\nchild u();\nendmodule\n')
    (tmp_path / 'child.sv').write_text('module child;\nwire [`WIDTH-1:0] value;\nendmodule\n')
    pre = tmp_path / 'pre.f'
    pre.write_text('top.sv\n+define+WIDTH=8\n' if late else '+define+WIDTH=8\ntop.sv\n')
    cp = run_cli(tmp_path, '-p', pre)
    if late:
        assert cp.returncode != 0 and 'Macro WIDTH' in cp.stderr
        assert not (tmp_path / 'out.f').exists()
    else:
        assert cp.returncode == 0, cp.stderr
        assert (tmp_path / 'out.f').read_text().splitlines()[0] == '+define+WIDTH=8'


def test_macro_provider_from_included_header_is_bound_to_parent(tmp_path):
    parent = tmp_path / 'top.sv'
    parent.write_text('`include "defs.svh"\nmodule top;\nchild u();\nendmodule\n')
    (tmp_path / 'defs.svh').write_text('`define FN(x) x\n')
    (tmp_path / 'child.sv').write_text('module child;\nwire x = `FN(1);\nendmodule\n')
    cp = run_cli(tmp_path, '-p', parent)
    assert cp.returncode == 0, cp.stderr
    assert (tmp_path / 'out.f').read_text().splitlines() == ['top.sv', 'child.sv']


def test_prelude_redefinition_keeps_actual_prior_provider(tmp_path):
    (tmp_path / 'first.svh').write_text('`define WIDTH 8\n')
    (tmp_path / 'middle.sv').write_text('module middle;\nwire [`WIDTH-1:0] value;\nendmodule\n')
    (tmp_path / 'last.svh').write_text('`define WIDTH 16\n')
    (tmp_path / 'top.sv').write_text('module top; endmodule\n')
    pre = tmp_path / 'pre.f'
    pre.write_text('first.svh\nmiddle.sv\nlast.svh\n')
    cp = run_cli(tmp_path, '-p', pre)
    assert cp.returncode == 0, cp.stderr
    assert (tmp_path / 'out.f').read_text().splitlines()[:3] == ['first.svh', 'middle.sv', 'last.svh']


def test_sort_cannot_silently_change_conditional_environment(tmp_path):
    (tmp_path / 'defs.sv').write_text('`define FLAG\nmodule defs; endmodule\n')
    (tmp_path / 'top.sv').write_text('module top;\n`ifdef FLAG\nwire x;\n`else\nwire y;\n`endif\nendmodule\n')
    cp = run_cli(tmp_path, '-t', 'top', 'defs')
    assert cp.returncode != 0 and 'Macro FLAG' in cp.stderr
    assert not (tmp_path / 'out.f').exists()


def test_real_instance_survives_same_name_scoped_call(tmp_path):
    (tmp_path / 'p.sv').write_text('package p; function void f(); endfunction endpackage\n')
    (tmp_path / 'f.sv').write_text('module f; endmodule\n')
    (tmp_path / 'top.sv').write_text('module top; initial p::f();\nf real_instance();\nendmodule\n')
    cp = run_cli(tmp_path)
    assert cp.returncode == 0, cp.stderr
    lines = (tmp_path / 'out.f').read_text().splitlines()
    assert set(lines) == {'p.sv', 'f.sv', 'top.sv'}


def test_missing_package_call_still_fails(tmp_path):
    (tmp_path / 'top.sv').write_text('module top; initial missing::f(); endmodule\n')
    cp = run_cli(tmp_path)
    assert cp.returncode != 0 and 'Not found module "missing"' in cp.stderr
    assert 'Not found module "f"' not in cp.stderr


@pytest.mark.parametrize('prelude', [False, True])
def test_macro_package_hard_cycle_is_an_error(tmp_path, prelude):
    parent = tmp_path / 'top.sv'
    parent.write_text('`define WIDTH 8\nmodule top;\nimport p::*;\nendmodule\n')
    (tmp_path / 'p.sv').write_text('package p;\nlocalparam int W = `WIDTH;\nendpackage\n')
    (tmp_path / 'out.f').write_text('old good output\n')
    args = ['-p', parent] if prelude else []
    cp = run_cli(tmp_path, *args)
    assert cp.returncode != 0 and 'WIDTH' in cp.stderr and 'acro' in cp.stderr
    assert (tmp_path / 'out.f').read_text() == 'old good output\n'
