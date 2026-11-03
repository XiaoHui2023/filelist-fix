from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def cli(work, *extra, expected=0):
    tops = [] if '-t' in extra or '--top' in extra else ['-t', 'probe']
    cp = subprocess.run([sys.executable, str(ROOT / 'src'), '-s', str(work), *tops,
                         '-o', str(work / 'out.f'), *map(str, extra)],
                        capture_output=True, text=True, encoding='utf-8', timeout=15)
    assert cp.returncode == expected, cp.stderr
    return cp


def probe_body(kind='ifndef'):
    if kind == 'ifdef':
        return '`ifdef FLAG\nset_leaf u();\n`else\nunset_leaf u();\n`endif\n'
    if kind == 'elsif':
        return '`ifdef NEVER\nmissing u();\n`elsif FLAG\nset_leaf u();\n`else\nunset_leaf u();\n`endif\n'
    return '`ifndef FLAG\nunset_leaf u();\n`else\nset_leaf u();\n`endif\n'


def fixtures(work, kind='ifndef'):
    (work / 'z_probe.sv').write_text('module probe;\n' + probe_body(kind) + 'endmodule\n')
    (work / 'a_defs.sv').write_text('`define FLAG\nmodule defs; endmodule\n')
    for name in ['set_leaf', 'unset_leaf']:
        (work / (name + '.sv')).write_text('module ' + name + '; endmodule\n')


@pytest.mark.parametrize('kind', ['ifdef', 'ifndef', 'elsif'])
def test_undefined_condition_needs_no_provider(tmp_path, kind):
    fixtures(tmp_path, kind)
    (tmp_path / 'a_defs.sv').unlink()
    cli(tmp_path)
    lines = (tmp_path / 'out.f').read_text().splitlines()
    assert lines == ['unset_leaf.sv', 'z_probe.sv']


@pytest.mark.parametrize('kind', ['ifdef', 'ifndef', 'elsif'])
@pytest.mark.parametrize('prelude', [False, True])
def test_future_definition_keeps_probe_undefined_cold_warm(tmp_path, kind, prelude):
    fixtures(tmp_path, kind)
    args = ['-t', 'probe', 'defs', '--save', tmp_path / 'cache.db']
    if prelude:
        (tmp_path / 'pre.f').write_text('z_probe.sv\na_defs.sv\n')
        args += ['-p', tmp_path / 'pre.f']
    for _ in range(2):
        cli(tmp_path, *args)
        lines = (tmp_path / 'out.f').read_text().splitlines()
        assert lines.index('z_probe.sv') < lines.index('a_defs.sv')
        assert 'unset_leaf.sv' in lines and 'set_leaf.sv' not in lines


def test_multiple_future_definitions_are_not_ambiguous_providers(tmp_path):
    fixtures(tmp_path)
    (tmp_path / 'b_later.sv').write_text('`define FLAG 2\nmodule later; endmodule\n')
    cli(tmp_path, '-t', 'probe', 'defs', 'later')
    lines = (tmp_path / 'out.f').read_text().splitlines()
    assert lines.index('z_probe.sv') < lines.index('a_defs.sv') < lines.index('b_later.sv')
    assert 'unset_leaf.sv' in lines and 'set_leaf.sv' not in lines


def test_top_input_order_changes_macro_branch_and_cache_context(tmp_path):
    fixtures(tmp_path)
    for tops, selected, excluded in [(['probe', 'defs'], 'unset_leaf.sv', 'set_leaf.sv'),
                                      (['defs', 'probe'], 'set_leaf.sv', 'unset_leaf.sv'),
                                      (['probe', 'defs'], 'unset_leaf.sv', 'set_leaf.sv')]:
        cli(tmp_path, '-t', *tops, '--save', tmp_path / 'cache.db')
        lines = (tmp_path / 'out.f').read_text().splitlines()
        assert selected in lines and excluded not in lines
        assert (lines.index('z_probe.sv') < lines.index('a_defs.sv')) == (tops[0] == 'probe')


@pytest.mark.parametrize('reset', ['undef FLAG', 'undefineall'])
def test_reset_then_probe_then_redefinition_follows_input(tmp_path, reset):
    fixtures(tmp_path)
    (tmp_path / 'first.sv').write_text('`define FLAG 1\nmodule first; endmodule\n')
    (tmp_path / 'kill.sv').write_text('`' + reset + '\nmodule kill; endmodule\n')
    for _ in range(2):
        cli(tmp_path, '-t', 'first', 'kill', 'probe', 'defs', '--save', tmp_path / 'cache.db')
        lines = (tmp_path / 'out.f').read_text().splitlines()
        positions = [lines.index(n) for n in ['first.sv', 'kill.sv', 'z_probe.sv', 'a_defs.sv']]
        assert positions == sorted(positions)
        assert 'unset_leaf.sv' in lines and 'set_leaf.sv' not in lines


def test_actual_macro_value_read_stays_between_redefinitions(tmp_path):
    (tmp_path / 'first.sv').write_text('`define WIDTH 8\nmodule first; endmodule\n')
    (tmp_path / 'z_probe.sv').write_text('module probe;\nlocalparam int W = `WIDTH;\nendmodule\n')
    (tmp_path / 'a_later.sv').write_text('`define WIDTH 16\nmodule later; endmodule\n')
    cli(tmp_path, '-t', 'first', 'probe', 'later')
    assert (tmp_path / 'out.f').read_text().splitlines() == ['first.sv', 'z_probe.sv', 'a_later.sv']


def test_conditional_before_module_dependency_definition_is_legal(tmp_path):
    (tmp_path / 'z_probe.sv').write_text('module probe;\nchild u();\n' +
        '`ifndef FLAG\nwire absent_branch;\n`endif\nendmodule\n')
    (tmp_path / 'a_child.sv').write_text('`define FLAG\nmodule child; endmodule\n')
    cli(tmp_path)
    assert (tmp_path / 'out.f').read_text().splitlines() == ['z_probe.sv', 'a_child.sv']


def test_included_condition_uses_host_input_position(tmp_path):
    fixtures(tmp_path)
    (tmp_path / 'condition.svh').write_text(probe_body())
    (tmp_path / 'z_probe.sv').write_text('module probe;\n`include "condition.svh"\nendmodule\n')
    for _ in range(2):
        cli(tmp_path, '-t', 'probe', 'defs', '--save', tmp_path / 'cache.db')
        lines = (tmp_path / 'out.f').read_text().splitlines()
        assert lines.index('z_probe.sv') < lines.index('a_defs.sv')
        assert 'unset_leaf.sv' in lines and 'set_leaf.sv' not in lines


def test_package_order_conflict_still_preserves_old_list(tmp_path):
    (tmp_path / 'probe.sv').write_text('module probe;\nimport p::*;\n`ifndef FLAG\nwire absent_branch;\n`endif\nendmodule\n')
    (tmp_path / 'p.sv').write_text('`define FLAG\npackage p; endpackage\n')
    (tmp_path / 'out.f').write_text('old valid output\n')
    cli(tmp_path, expected=1)
    assert (tmp_path / 'out.f').read_text() == 'old valid output\n'


def test_dead_nested_condition_is_not_a_state_observation(tmp_path):
    fixtures(tmp_path)
    (tmp_path / 'z_probe.sv').write_text('module probe;\n`ifdef NEVER\n`ifdef FLAG\nmissing u();\n`endif\n`endif\nendmodule\n')
    cli(tmp_path, '-t', 'probe', 'defs')
    assert set((tmp_path / 'out.f').read_text().splitlines()) == {'z_probe.sv', 'a_defs.sv'}


def test_probe_metadata_is_separate_from_actual_expansion():
    from verilog_text.preproc import PreprocDirectiveParser
    parser = PreprocDirectiveParser({'KNOWN': '8'})
    for line in ['`ifdef KNOWN', 'wire [`KNOWN-1:0] value;', '`endif',
                 '`ifndef OPTIONAL', 'wire fallback;', '`endif']:
        parser.handle_directive_line(line)
    symbols = parser.macro_symbols()
    assert symbols['macro_uses'] == ['KNOWN']
    assert symbols['macro_condition_defined'] == ['KNOWN']
    assert symbols['macro_condition_undefined'] == ['OPTIONAL']


def test_unrelated_macro_writer_can_move_for_package_dependency(tmp_path):
    (tmp_path / 'probe.sv').write_text('`define OWN 1\nmodule probe;\nimport p::*;\n'
        '`ifndef OPTIONAL\nwire fallback;\n`endif\nendmodule\n')
    (tmp_path / 'p.sv').write_text('`define OTHER 1\npackage p; endpackage\n')
    cli(tmp_path)
    assert (tmp_path / 'out.f').read_text().splitlines() == ['p.sv', 'probe.sv']


def test_explicit_prelude_define_and_later_source_redefinition(tmp_path):
    fixtures(tmp_path)
    (tmp_path / 'pre.f').write_text('+define+FLAG\nz_probe.sv\na_defs.sv\n')
    cli(tmp_path, '-p', tmp_path / 'pre.f', '-t', 'probe', 'defs')
    lines = (tmp_path / 'out.f').read_text().splitlines()
    assert lines.index('z_probe.sv') < lines.index('a_defs.sv')
    assert 'set_leaf.sv' in lines and 'unset_leaf.sv' not in lines


def test_repeated_header_macro_writers_keep_input_order(tmp_path):
    (tmp_path / 'shared.svh').write_text('`define WIDTH 8\n')
    (tmp_path / 'z_probe.sv').write_text('`include "shared.svh"\nmodule probe;\nreplica u();\nendmodule\n')
    (tmp_path / 'a_replica.sv').write_text('`include "shared.svh"\nmodule replica;\nlocalparam int VALUE=`WIDTH;\nendmodule\n')
    cli(tmp_path)
    assert (tmp_path / 'out.f').read_text().splitlines() == ['z_probe.sv', 'a_replica.sv']
