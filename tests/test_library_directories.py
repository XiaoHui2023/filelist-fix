from pathlib import Path
import os
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run(work, *, mode=True, expected=0, tops='top', extra=()):
    args = [sys.executable, str(ROOT / 'src'), '-s', str(work), '-t', tops,
            '-p', str(work / 'pre.f'), '-o', str(work / 'out.f'), '--save', str(work / 'cache.db')]
    if mode:
        args.append('--compact-libs')
    args.extend(map(str, extra))
    cp = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}, timeout=20)
    assert cp.returncode == expected, cp.stderr
    return (work / 'out.f').read_text().splitlines() if not expected else cp


def fixture(work, *, explicit=True, marked=False, count=8):
    lib = work / 'models'; lib.mkdir()
    names = [f'cell{i}' for i in range(count)]
    for name in names:
        text = f'module {name}; specify specparam T=1; endspecify endmodule\n'
        if marked:
            text = '`celldefine\n' + text + '`endcelldefine\n'
        (lib / (name + '.v')).write_text(text)
    (work / 'top.sv').write_text('module top;\n' + ''.join(f'{name} u{i}();\n' for i, name in enumerate(names)) + 'endmodule\n')
    (work / 'pre.f').write_text(''.join('-v models/' + name + '.v\n' for name in names) if explicit else '')
    return lib


@pytest.mark.parametrize('marked,explicit', [(False,True),(True,False),(True,True)])
def test_library_directory_compression_cold_warm(tmp_path, marked, explicit):
    fixture(tmp_path, explicit=explicit, marked=marked)
    for _ in range(2):
        assert run(tmp_path) == ['+libext+.v', '-y models', 'top.sv']


def test_disabled_mode_preserves_all_explicit_inputs(tmp_path):
    fixture(tmp_path)
    lines = run(tmp_path, mode=False)
    assert lines == ['-v models/cell' + str(i) + '.v' for i in range(8)] + ['top.sv']


@pytest.mark.parametrize('syntax', ['-y models +libext+ .v\n', '-y models\n+libext+ .v\n', '+libext+.v\n-y models\n'])
def test_library_syntax_normalizes_and_collects_without_plain_files(tmp_path, syntax):
    fixture(tmp_path)
    (tmp_path / 'pre.f').write_text(syntax)
    assert run(tmp_path) == ['+libext+.v', '-y models', 'top.sv']


def test_plain_dependency_compacts_without_requiring_device_markers(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/cell0.v').write_text('module cell0; specify specparam T=1; endspecify endmodule\n')
    lines = run(tmp_path)
    assert lines == ['+libext+.v', '-y models', 'top.sv']


@pytest.mark.parametrize('content', [
    'module cell0; endmodule\nmodule helper; endmodule\n',
    '`define WIDTH 8\nmodule cell0; endmodule\n',
    '`ifdef ON\nmodule cell0; endmodule\n`else\nmodule cell0; endmodule\n`endif\n',
    '`include "shared.svh"\nmodule cell0; endmodule\n',
    '`timescale 1ns/1ps\nmodule cell0; endmodule\n',
])
def test_unsafe_files_retain_explicit_library_role(tmp_path, content):
    fixture(tmp_path)
    (tmp_path / 'models/shared.svh').write_text('// header\n')
    (tmp_path / 'models/cell0.v').write_text(content)
    lines = run(tmp_path)
    assert '-v models/cell0.v' in lines
    if '`include' in content or '`timescale' in content:
        assert not any(line.startswith('-y') for line in lines)
    else:
        assert '-y models' in lines


def test_nonmatching_unit_filename_and_mixed_directory_fall_back(tmp_path):
    lib = fixture(tmp_path)
    (lib / 'cell0.v').rename(lib / 'bundle.v')
    (tmp_path / 'pre.f').write_text((tmp_path / 'pre.f').read_text().replace('cell0.v', 'bundle.v'))
    lines = run(tmp_path)
    assert lines == ['+libext+.v', '-v models/bundle.v', '-y models', 'top.sv']


def test_unreferenced_neighbor_does_not_veto_directory_promotion(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'models/extra.v').write_text('module extra; endmodule\n')
    assert run(tmp_path) == ['+libext+.v', '-y models', 'top.sv']


def test_excluded_cell_is_not_reexposed_by_new_directory(tmp_path):
    fixture(tmp_path)
    excluded = tmp_path / 'models/extra.v'
    excluded.write_text('`celldefine\nmodule extra; endmodule\n`endcelldefine\n')
    assert not any(line.startswith('-y') for line in run(tmp_path, extra=['-x', excluded]))


def test_ordinary_conflicts_and_missing_dependencies_preserve_output(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'models/cell0.v').write_text('module cell0; missing u(); endmodule\n')
    (tmp_path / 'out.f').write_text('previous\n')
    assert 'missing' in run(tmp_path, expected=1).stderr
    assert (tmp_path / 'out.f').read_text() == 'previous\n'
    (tmp_path / 'pre.f').write_text('')
    (tmp_path / 'models/cell0.v').write_text('module cell0; endmodule\n')
    (tmp_path / 'other').mkdir()
    (tmp_path / 'other/cell0.v').write_text('module cell0; endmodule\n')
    assert 'Duplicate definition' in run(tmp_path, expected=1).stderr


def test_configured_library_directory_order_is_explicit_precedence(tmp_path):
    fixture(tmp_path)
    other = tmp_path / 'other'; other.mkdir()
    (other / 'cell0.v').write_text('module cell0; endmodule\n')
    (tmp_path / 'pre.f').write_text('+libext+.v\n-y other\n-y models\n')
    assert run(tmp_path) == ['+libext+.v', '-y other', '-y models', 'top.sv']
    assert 'Duplicate definition' in run(tmp_path, mode=False, expected=1).stderr


def test_markers_in_comments_strings_or_inactive_branches_are_not_evidence(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/cell0.v').write_text('// `celldefine\nmodule cell0; string s="`celldefine"; endmodule\n// `endcelldefine\n')
    lines = run(tmp_path)
    assert 'models/cell0.v' in lines and '-y models' in lines
    from verilog_text.library_cells import inspect_library_source
    assert inspect_library_source((tmp_path / 'models/cell0.v').read_text())[1] == []


def test_top_marked_as_cell_remains_ordinary_root(tmp_path):
    fixture(tmp_path, explicit=False, marked=True)
    (tmp_path / 'top.sv').write_text('`celldefine\nmodule top; cell0 u(); endmodule\n`endcelldefine\n')
    assert run(tmp_path)[-1] == 'top.sv'


def test_directory_with_spaces_and_absolute_paths(tmp_path):
    lib = fixture(tmp_path)
    lib.rename(tmp_path / 'models space')
    (tmp_path / 'pre.f').write_text(''.join('-v "models space/cell' + str(i) + '.v"\n' for i in range(8)))
    assert run(tmp_path) == ['+libext+.v', '-y "models space"', 'top.sv']
    lines = run(tmp_path, extra=['--path-style', 'absolute'])
    assert lines == ['+libext+.v', '-y "' + str(tmp_path / 'models space') + '"', str(tmp_path / 'top.sv')]


def test_conversion_cannot_move_explicit_provider_behind_existing_directory(tmp_path):
    fixture(tmp_path)
    earlier = tmp_path / 'earlier'; earlier.mkdir()
    (earlier / 'cell0.v').write_text('module cell0; endmodule\n')
    pre = tmp_path / 'pre.f'
    pre.write_text('+libext+.v\n-y earlier\n' + pre.read_text())
    lines = run(tmp_path)
    assert '-v models/cell0.v' in lines and '-y models' not in lines


def test_library_packages_keep_strict_uniqueness(tmp_path):
    fixture(tmp_path)
    for i in range(2):
        path = tmp_path / f'models/cell{i}.v'
        path.write_text(path.read_text() + 'package p; endpackage\n')
    assert 'Duplicate definition' in run(tmp_path, expected=1).stderr


def test_global_compiler_state_does_not_promote_ordinary_cell_file(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/cell0.v').write_text('`timescale 1ns/1ps\n`celldefine\nmodule cell0; endmodule\n`endcelldefine\n')
    original = run(tmp_path, mode=False)
    assert run(tmp_path) == original


@pytest.mark.parametrize('prefix', ['`timescale 1ns/1ps\n', '`default_nettype none\n', '`include "state.svh"\n'])
def test_shared_compiler_context_preserves_ordinary_dependencies(tmp_path, prefix):
    fixture(tmp_path, explicit=False, marked=True)
    (tmp_path / 'state.svh').write_text('`timescale 1ns/1ps\n')
    top = tmp_path / 'top.sv'
    top.write_text(prefix + top.read_text())
    assert run(tmp_path) == run(tmp_path, mode=False)


@pytest.mark.parametrize('outside', ['typedef int shared_t;', 'import dep::*;',
                                      'function int shared_f(); return 1; endfunction'])
def test_compilation_unit_exports_remain_eager(tmp_path, outside):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'dep.sv').write_text('package dep; endpackage\n')
    path = tmp_path / 'models/cell0.v'
    path.write_text(outside + '\n' + path.read_text())
    lines = run(tmp_path)
    assert 'models/cell0.v' in lines and '-v models/cell0.v' not in lines
    assert '-y models' not in lines


def test_explicit_ordinary_prelude_stays_eager(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'pre.f').write_text('models/cell0.v\n')
    lines = run(tmp_path)
    assert 'models/cell0.v' in lines and '-y models' in lines


def test_malformed_unused_neighbor_is_not_loaded(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/unused.v').write_text('`timescale 1ns/1ps\nmodule unused; missing u();\n')
    assert run(tmp_path) == ['+libext+.v', '-y models', 'top.sv']


def test_plain_duplicate_definitions_remain_errors_in_compact_mode(tmp_path):
    fixture(tmp_path, explicit=False, marked=True)
    (tmp_path / 'other').mkdir()
    (tmp_path / 'other/cell0.v').write_text('`celldefine\nmodule cell0; endmodule\n`endcelldefine\n')
    (tmp_path / 'out.f').write_text('previous\n')
    assert 'Duplicate definition' in run(tmp_path, expected=1).stderr
    assert (tmp_path / 'out.f').read_text() == 'previous\n'


@pytest.mark.parametrize('feature,source', [
    ('celldefine', '`celldefine\nmodule cell0; endmodule\n`endcelldefine\n'),
    ('timing-model', 'module cell0; specparam T=1; endmodule\n'),
    ('udp', 'primitive cell0(q,a); output q; input a; table 0 : 0; 1 : 1; endtable endprimitive\n'),
    ('gate-primitive', 'module cell0; wire a,b,q; and u(q,a,b); endmodule\n'),
    ('model-attribute', '(* syn_black_box *) module cell0; endmodule\n'),
    ('supply-or-charge-net', 'module cell0; supply1 vdd; endmodule\n'),
    ('drive-or-charge-strength', 'module cell0; wire q,a; assign (strong1, weak0) q=a; endmodule\n'),
])
def test_each_library_feature_is_sufficient_on_its_own(tmp_path, feature, source):
    from verilog_text.library_cells import inspect_library_source
    profile = inspect_library_source(source)
    assert profile[5] == [feature]
    assert profile[2]
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/cell0.v').write_text(source)
    assert run(tmp_path) == ['+libext+.v', '-y models', 'top.sv']


@pytest.mark.parametrize('source', [
    '`ifdef FLAG\n`celldefine\nmodule cell0; endmodule\n`endcelldefine\n`endif\n',
    '`timescale 1ns/1ps\nmodule cell0; specify specparam T=1; endspecify endmodule\n',
    'module cell0; endmodule\nmodule helper; supply0 gnd; endmodule\n',
    '`include "cell_body.vh"\nmodule cell0; supply0 gnd; endmodule\n',
])
def test_library_recognition_is_independent_of_conversion_safety(source):
    from verilog_text.library_cells import inspect_library_source
    profile = inspect_library_source(source)
    assert profile[5] and not profile[2]


def test_unfeatured_rtl_is_not_automatically_called_a_device_library(tmp_path):
    fixture(tmp_path, explicit=False)
    for path in (tmp_path / 'models').iterdir():
        path.write_text(f'module {path.stem}; wire q,a; assign q=a; endmodule\n')
    assert not any(line.startswith(('-y', '-v')) for line in run(tmp_path))


def test_classification_and_retention_counts_are_available_in_existing_log(tmp_path):
    fixture(tmp_path, explicit=False)
    p = tmp_path / 'models/cell0.v'
    p.write_text('`timescale 1ns/1ps\n' + p.read_text())
    run(tmp_path, extra=['-l', tmp_path / 'run.log'])
    text = (tmp_path / 'run.log').read_text(encoding='utf-8')
    assert 'recognized_files=8' in text and 'compacted_files=0' in text
    assert 'shared compilation context' in text and 'timing-model' in text


@pytest.mark.parametrize('compact', [False, True])
def test_retained_plain_paths_with_spaces_compile_as_one_argument(tmp_path, compact):
    lib = fixture(tmp_path, explicit=False)
    lib.rename(tmp_path / 'models space')
    (tmp_path / 'pre.f').write_text('"models space/cell0.v"\n')
    top = tmp_path / 'top.sv'
    top.write_text('`default_nettype none\n' + top.read_text())
    lines = run(tmp_path, mode=compact)
    assert all('"models space/cell' + str(i) + '.v"' in lines for i in range(8))


@pytest.mark.parametrize('source', [
    'module m; wire [1:0] q,a; buf u[1:0](q,a); endmodule',
    '// synthesis syn_black_box\nmodule m; endmodule',
])
def test_gate_arrays_and_structured_model_pragmas_are_features(source):
    from verilog_text.library_cells import inspect_library_source
    assert inspect_library_source(source)[5]


def test_ordinary_comments_and_strings_are_not_model_features():
    from verilog_text.library_cells import inspect_library_source
    source = '// specify primitive blackbox\nmodule m; string s="// synthesis syn_black_box"; endmodule'
    assert inspect_library_source(source)[5] == []


@pytest.mark.parametrize('shadow', [False, True])
def test_existing_extension_order_is_preserved_and_audited(tmp_path, shadow):
    fixture(tmp_path)
    pre = tmp_path / 'pre.f'
    pre.write_text('+libext+.model\n' + pre.read_text())
    if shadow:
        (tmp_path / 'models/cell0.model').write_text('module cell0; endmodule\n')
    lines = run(tmp_path)
    if shadow:
        assert '-y models' not in lines and '-v models/cell0.v' in lines
    else:
        assert '-y models' in lines
    assert lines[0] == ('+libext+.model' if shadow else '+libext+.model+.v')


@pytest.mark.parametrize('marked', [False, True])
def test_warm_model_hints_do_not_hide_new_duplicate_candidates(tmp_path, marked):
    fixture(tmp_path, explicit=False, marked=marked)
    run(tmp_path)
    preserved = (tmp_path / 'out.f').read_bytes()
    (tmp_path / 'other').mkdir()
    text = (tmp_path / 'models/cell0.v').read_text()
    (tmp_path / 'other/cell0.v').write_text(text)
    assert 'Duplicate definition' in run(tmp_path, expected=1).stderr
    assert (tmp_path / 'out.f').read_bytes() == preserved
