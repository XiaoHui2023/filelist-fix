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
        args.append('--library-directories')
    args.extend(map(str, extra))
    cp = subprocess.run(args, capture_output=True, text=True, encoding='utf-8',
                        env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONIOENCODING': 'utf-8'}, timeout=20)
    assert cp.returncode == expected, cp.stderr
    return (work / 'out.f').read_text().splitlines() if not expected else cp


def fixture(work, *, explicit=True, marked=False, count=8):
    lib = work / 'models'; lib.mkdir()
    names = [f'cell{i}' for i in range(count)]
    for name in names:
        text = f'module {name}; endmodule\n'
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


def test_specify_alone_does_not_reclassify_ordinary_rtl(tmp_path):
    fixture(tmp_path, explicit=False)
    (tmp_path / 'models/cell0.v').write_text('module cell0; specify specparam T=1; endspecify endmodule\n')
    lines = run(tmp_path)
    assert not any(line.startswith(('-y', '-v')) for line in lines)
    assert 'models/cell0.v' in lines


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
    assert not any(line.startswith('-y') for line in lines)


def test_nonmatching_unit_filename_and_mixed_directory_fall_back(tmp_path):
    lib = fixture(tmp_path)
    (lib / 'cell0.v').rename(lib / 'bundle.v')
    (tmp_path / 'pre.f').write_text((tmp_path / 'pre.f').read_text().replace('cell0.v', 'bundle.v'))
    lines = run(tmp_path)
    assert '-v models/bundle.v' in lines and not any(line.startswith('-y') for line in lines)


def test_unmarked_neighbor_prevents_directory_promotion(tmp_path):
    fixture(tmp_path)
    (tmp_path / 'models/extra.v').write_text('module extra; endmodule\n')
    assert not any(line.startswith('-y') for line in run(tmp_path))


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
    assert 'models/cell0.v' in lines and not any(line.startswith('-y') for line in lines)


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
