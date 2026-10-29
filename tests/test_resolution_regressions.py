from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(root, *extra):
    return subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(root / 'rtl'),
                           '-t', 'top', '-o', str(root / 'out.f'), *map(str, extra)],
                          cwd=ROOT, capture_output=True, text=True, encoding='utf-8')


def setup(root):
    (root / 'rtl').mkdir()
    return root / 'rtl'


@pytest.mark.parametrize('padding', [0, 20000, 600000])
def test_located_definition_survives_procedural_squeeze(tmp_path, padding):
    rtl = setup(tmp_path)
    # Legal adjacent closing keywords, common in generated compact RTL.
    (rtl / 'netlist.sv').write_text('module helper;\ninitial begin\n' +
        '  ;\n' * padding + 'end endmodule\nmodule top;\nhelper u();\nendmodule\n')
    for _ in range(2):
        result = cli(tmp_path, '--save', tmp_path / 'cache.db')
        assert result.returncode == 0, result.stderr
        assert (tmp_path / 'out.f').read_text().splitlines() == ['rtl/netlist.sv']


@pytest.mark.parametrize('statement', [
    'dep::item_t value;',
    'localparam int W = dep::WIDTH;',
    'initial $display("%0d", dep::WIDTH);',
    'function dep::item_t make(); return dep::WIDTH; endfunction',
    'leaf #(.W(dep::WIDTH)) u();',
])
def test_scoped_package_reference_enters_closure(tmp_path, statement):
    rtl = setup(tmp_path)
    (rtl / 'top.sv').write_text('module top;\n' + statement + '\nendmodule\n')
    (rtl / 'dep.sv').write_text('package dep; typedef int item_t; parameter WIDTH=1; endpackage\n')
    (rtl / 'leaf.sv').write_text('module leaf #(parameter W=1); endmodule\n')
    for _ in range(2):
        result = cli(tmp_path, '--save', tmp_path / 'cache.db')
        assert result.returncode == 0, result.stderr
        lines = (tmp_path / 'out.f').read_text().splitlines()
        assert lines.index('rtl/dep.sv') < lines.index('rtl/top.sv')


def test_missing_scoped_package_fails_without_overwriting(tmp_path):
    rtl = setup(tmp_path)
    (rtl / 'top.sv').write_text('module top;\nlocalparam int W = absent::WIDTH;\nendmodule\n')
    (tmp_path / 'out.f').write_text('old output\n')
    result = cli(tmp_path)
    assert result.returncode != 0 and 'absent' in result.stderr
    assert (tmp_path / 'out.f').read_text() == 'old output\n'


def test_library_directory_and_custom_extension_enter_closure(tmp_path):
    rtl = setup(tmp_path)
    lib = tmp_path / 'lib with spaces'
    lib.mkdir()
    (rtl / 'top.sv').write_text('module top;\ncell_a u();\nendmodule\n')
    (lib / 'cell_a.model').write_text('module cell_a;\ncell_b u();\nendmodule\n')
    (lib / 'cell_b.model').write_text('module cell_b; endmodule\n')
    (tmp_path / 'pre.f').write_text('-y "lib with spaces"\n+libext+.model\n')
    for _ in range(2):
        result = cli(tmp_path, '-p', tmp_path / 'pre.f', '--save', tmp_path / 'cache.db')
        assert result.returncode == 0, result.stderr
        text = (tmp_path / 'out.f').read_text()
        assert text.index('cell_b.model') < text.index('cell_a.model') < text.index('top.sv')


@pytest.mark.parametrize('body', [
    'class C; static function int f(); return 1; endfunction endclass\ninitial $display("%0d", C::f());',
    'class C; parameter W=1; endclass\ntypedef C T;\ninitial $display("%0d", T::W);',
    '/* fake::x */\ninitial $display("fake::x");',
    '`ifdef NEVER\nmissing::t x;\n`endif',
])
def test_non_package_scopes_are_not_dependencies(tmp_path, body):
    rtl = setup(tmp_path)
    (rtl / 'top.sv').write_text('module top;\n' + body + '\nendmodule\n')
    result = cli(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'out.f').read_text().splitlines() == ['rtl/top.sv']


def test_package_port_and_class_chain(tmp_path):
    rtl = setup(tmp_path)
    (rtl / 'top.sv').write_text('module top(input dep::item_t x);\ninitial $display("%d", dep :: C :: W);\nendmodule\n')
    (rtl / 'dep.sv').write_text('package dep; typedef int item_t; class C; parameter W=1; endclass endpackage\n')
    result = cli(tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / 'out.f').read_text().splitlines() == ['rtl/dep.sv', 'rtl/top.sv']


def test_wildcard_imported_class_scope_is_not_a_package(tmp_path):
    rtl = setup(tmp_path)
    (rtl / 'dep.sv').write_text('package dep; class C; static function int f(); return 1; endfunction endclass endpackage\n')
    (rtl / 'top.sv').write_text('module top;\nimport dep::*;\ninitial $display("%d", C::f());\nendmodule\n')
    args = ['--save', tmp_path / 'cache.db']
    for _ in range(2):
        result = cli(tmp_path, *args)
        assert result.returncode == 0, result.stderr
        assert (tmp_path / 'out.f').read_text().splitlines() == ['rtl/dep.sv', 'rtl/top.sv']
    (rtl / 'top.sv').write_text('module top;\nimport dep::*;\ninitial $display("%d", missing::W);\nendmodule\n')
    assert cli(tmp_path, *args).returncode != 0


def test_imported_class_name_does_not_erase_real_module_edge(tmp_path):
    rtl = setup(tmp_path)
    (rtl / 'dep.sv').write_text('package dep; class C; parameter W=1; endclass endpackage\n')
    (rtl / 'C.sv').write_text('module C(input int x); endmodule\n')
    (rtl / 'top.sv').write_text('module top;\nimport dep::*;\nC u(.x(C::W));\nendmodule\n')
    result = cli(tmp_path)
    assert result.returncode == 0, result.stderr
    assert 'rtl/C.sv' in (tmp_path / 'out.f').read_text().splitlines()


def library_fixture(root):
    rtl = setup(root)
    (rtl / 'top.sv').write_text('module top;\ncell_a u();\nendmodule\n')
    lib = root / 'lib'
    lib.mkdir()
    (lib / 'cell_a.v').write_text('module cell_a; endmodule\n')
    pre = root / 'pre.f'
    pre.write_text('-y lib\n')
    return lib, pre


def test_library_cache_respects_removed_scope_and_exclusion(tmp_path):
    lib, pre = library_fixture(tmp_path)
    args = ['-p', pre, '--save', tmp_path / 'cache.db']
    assert cli(tmp_path, *args).returncode == 0
    original = (tmp_path / 'out.f').read_bytes()
    for extra, config in [(['--exclude', lib], '-y lib\n'),
                          ([], ''), ([], '-y lib\n+libext+.sv\n')]:
        pre.write_text(config)
        result = cli(tmp_path, *args, *extra)
        assert result.returncode != 0 and 'cell_a' in result.stderr
        assert (tmp_path / 'out.f').read_bytes() == original


def test_duplicate_libraries_are_an_error(tmp_path):
    lib, pre = library_fixture(tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'cell_a.v').write_text((lib / 'cell_a.v').read_text())
    pre.write_text('-y lib\n-y other\n')
    result = cli(tmp_path, '-p', pre)
    assert result.returncode != 0 and 'cell_a' in result.stderr
    assert not (tmp_path / 'out.f').exists()
    assert cli(tmp_path, '-p', pre, '--exclude', other).returncode == 0


def test_warm_library_hint_does_not_hide_new_duplicate(tmp_path):
    lib, pre = library_fixture(tmp_path)
    other = tmp_path / 'other'
    other.mkdir()
    pre.write_text('-y lib\n-y other\n')
    args = ['-p', pre, '--save', tmp_path / 'cache.db']
    assert cli(tmp_path, *args).returncode == 0
    (other / 'cell_a.v').write_text((lib / 'cell_a.v').read_text())
    result = cli(tmp_path, *args)
    assert result.returncode != 0 and 'cell_a' in result.stderr


def test_nested_library_configuration_and_unused_files(tmp_path):
    lib, pre = library_fixture(tmp_path)
    (lib / 'unused.v').write_text('module unused;\nabsent u();\nendmodule\n')
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'nested.f').write_text('-y ../lib\n+libext+v\n')
    pre.write_text('-f config/nested.f\n')
    result = cli(tmp_path, '-p', pre)
    assert result.returncode == 0, result.stderr
    assert 'unused.v' not in (tmp_path / 'out.f').read_text()
